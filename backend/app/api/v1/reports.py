import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, or_, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_staff_or_admin, require_admin
from app.core.clock import organization_today
from app.core.config import settings
from app.core.database import get_db
from app.models.customer import CustomerAccount
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.plan import Plan, BillingCadence
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.schemas.report import (
    DashboardSummaryResponse,
    DrillDownResponse,
    DrillDownItemResponse,
)
from app.services.billing import _load_pricing_rules, _subscription_options, calculate_subscription_charge

router = APIRouter()
CENT = Decimal("0.01")


def _resolve_period_dates(
    period: Optional[str],
    start_date: Optional[date],
    end_date: Optional[date],
    today: date,
) -> tuple[date, date, str]:
    if start_date and end_date:
        return start_date, end_date, "custom"

    p = (period or "this_month").lower().strip()
    if p == "last_month":
        # First day of previous month
        first_this_month = today.replace(day=1)
        last_day_prev_month = first_this_month - timedelta(days=1)
        p_start = last_day_prev_month.replace(day=1)
        p_end = last_day_prev_month
        return p_start, p_end, "last_month"
    elif p == "this_quarter":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        p_start = today.replace(month=quarter_start_month, day=1)
        p_end = today
        return p_start, p_end, "this_quarter"
    elif p == "this_year":
        p_start = today.replace(month=1, day=1)
        p_end = today
        return p_start, p_end, "this_year"
    elif p == "all_time":
        p_start = date(2020, 1, 1)
        p_end = today
        return p_start, p_end, "all_time"
    else:  # default: this_month
        p_start = today.replace(day=1)
        p_end = today
        return p_start, p_end, "this_month"


@router.get("/summary", response_model=DashboardSummaryResponse, tags=["Reports"])
async def get_dashboard_summary(
    period: Optional[str] = Query("this_month", description="this_month, last_month, this_quarter, this_year, all_time, custom"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    """
    Finance & Operations Summary Dashboard with configurable reporting periods.
    Explicitly separates Invoiced Revenue (billing demands) from Cash Collected (actual receipts net of refunds).
    """
    today = organization_today()
    p_start, p_end, resolved_period = _resolve_period_dates(period, start_date, end_date, today)

    active_subscription_count = await db.scalar(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.ACTIVE)
    )

    monthly_run_rate = Decimal("0.00")
    if user.role == UserRole.ADMIN:
        active_query = (
            select(Subscription)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .options(*_subscription_options())
            .order_by(func.coalesce(Subscription.next_billing_date, Subscription.start_date), Subscription.subscription_number)
        )
        active_subscriptions = (await db.execute(active_query)).scalars().all()
        tax_map, default_tax_rule, discount_rules, redemption_counts = await _load_pricing_rules(db)
        for subscription in active_subscriptions:
            if subscription.customer_account and subscription.customer_account.currency != settings.ORGANIZATION_CURRENCY:
                continue
            charge = calculate_subscription_charge(
                subscription,
                tax_map=tax_map,
                default_tax_rule=default_tax_rule,
                discount_rules=discount_rules,
                redemption_counts=redemption_counts,
                as_of=today,
            )
            amount = max(Decimal("0.00"), charge.subtotal - charge.discount)
            cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
            if cadence == BillingCadence.DAILY:
                amount *= Decimal("30")
            elif cadence == BillingCadence.WEEKLY:
                amount *= Decimal("52") / Decimal("12")
            elif cadence == BillingCadence.YEARLY:
                amount /= Decimal("12")
            monthly_run_rate += amount
            if charge.discount_rule and not charge.warnings:
                redemption_counts[charge.discount_rule.id] = redemption_counts.get(charge.discount_rule.id, 0) + 1

    overdue_rows = (await db.execute(
        select(Invoice.total_amount, Invoice.paid_amount)
        .where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < today,
            Invoice.paid_amount < Invoice.total_amount,
            Invoice.currency == settings.ORGANIZATION_CURRENCY,
        )
    )).all()
    overdue_balance = sum(
        (Decimal(str(total)) - Decimal(str(paid)) for total, paid in overdue_rows),
        Decimal("0.00"),
    )

    overdue_count = await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < today,
            Invoice.paid_amount < Invoice.total_amount,
        )
    )
    pending_quotes = await db.scalar(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.QUOTATION)
    )
    renewals_due = await db.scalar(
        select(func.count(Subscription.id)).where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            func.coalesce(Subscription.next_billing_date, Subscription.start_date) >= today,
            func.coalesce(Subscription.next_billing_date, Subscription.start_date) <= today + timedelta(days=7),
        )
    )

    invoiced_revenue = None
    cash_collected = None
    outstanding_balance = None
    if user.role == UserRole.ADMIN:
        # Invoiced revenue within chosen date range
        invoiced_revenue = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                Invoice.issue_date >= p_start,
                Invoice.issue_date <= p_end,
                Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.PAID]),
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )

        # Cash collected within chosen date range (settled payments minus reversals)
        cash_collected = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(
                Payment.payment_date >= p_start,
                Payment.payment_date <= p_end,
                Payment.is_reversed.is_(False),
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )

        # Total outstanding open balance as of today
        outstanding_balance = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0)).where(
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.total_amount > Invoice.paid_amount,
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )

    mrr = monthly_run_rate.quantize(CENT, rounding=ROUND_HALF_UP) if user.role == UserRole.ADMIN else None

    return DashboardSummaryResponse(
        currency=settings.ORGANIZATION_CURRENCY,
        period=resolved_period,
        period_start=p_start,
        period_end=p_end,
        active_subscription_count=active_subscription_count or 0,
        monthly_recurring_revenue=mrr,
        invoiced_revenue=invoiced_revenue,
        invoiced_mtd=invoiced_revenue,  # Alias for backward compatibility
        cash_collected=cash_collected,
        cash_collected_mtd=cash_collected,  # Alias for backward compatibility
        outstanding_balance=outstanding_balance,
        overdue_balance=overdue_balance if user.role == UserRole.ADMIN else None,
        overdue_invoice_count=overdue_count or 0,
        pending_quotes_count=pending_quotes or 0,
        renewals_due_7d_count=renewals_due or 0,
    )


@router.get("/drill-down", response_model=DrillDownResponse, tags=["Reports"])
async def get_drill_down_report(
    metric: str = Query("invoiced", description="invoiced, collected, outstanding, overdue, subscriptions, mrr, all"),
    period: Optional[str] = Query("this_month"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    plan_id: Optional[uuid.UUID] = Query(None),
    customer_account_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """
    Traceable Drill-Down Ledger for Finance Verification.
    Allows drill-down from any dashboard summary metric into exact underlying invoices, payments, or subscriptions.
    """
    today = organization_today()
    p_start, p_end, _ = _resolve_period_dates(period, start_date, end_date, today)

    m = metric.lower().strip()
    items: List[DrillDownItemResponse] = []
    total_amount = Decimal("0.00")

    if m in ("collected", "cash_collected"):
        # Query Payments
        query = (
            select(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
            .options(
                selectinload(Payment.invoice).selectinload(Invoice.customer_account),
                selectinload(Payment.reversal),
            )
            .where(
                Payment.payment_date >= p_start,
                Payment.payment_date <= p_end,
            )
            .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
        )
        if customer_account_id:
            query = query.where(Invoice.customer_account_id == customer_account_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Invoice.invoice_number.ilike(term),
                    CustomerAccount.company_name.ilike(term),
                    Payment.reference_note.ilike(term),
                )
            )

        pay_results = (await db.execute(query)).scalars().all()
        for p in pay_results:
            inv = p.invoice
            cust = inv.customer_account.company_name if inv and inv.customer_account else "Customer"
            amt = p.amount if not p.is_reversed else -p.amount
            total_amount += amt
            items.append(
                DrillDownItemResponse(
                    id=str(p.id),
                    entity_type="payment",
                    reference_number=f"PAY-{inv.invoice_number if inv else p.id.hex[:6].upper()}",
                    customer_name=cust,
                    customer_account_id=inv.customer_account_id if inv else None,
                    plan_name="Remittance",
                    date=p.payment_date,
                    metric_category="Cash Collections",
                    status="Reversed" if p.is_reversed else "Settled",
                    currency=inv.currency if inv else "USD",
                    amount=p.amount,
                    paid_amount=p.amount,
                    balance=Decimal("0.00"),
                )
            )

    elif m in ("subscriptions", "mrr"):
        # Query Active Subscriptions
        query = (
            select(Subscription)
            .options(*_subscription_options())
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .order_by(Subscription.subscription_number)
        )
        if plan_id:
            query = query.where(Subscription.plan_id == plan_id)
        if customer_account_id:
            query = query.where(Subscription.customer_account_id == customer_account_id)
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.join(CustomerAccount, Subscription.customer_account_id == CustomerAccount.id).where(
                or_(
                    Subscription.subscription_number.ilike(term),
                    CustomerAccount.company_name.ilike(term),
                )
            )

        subs = (await db.execute(query)).scalars().all()
        for sub in subs:
            cust = sub.customer_account.company_name if sub.customer_account else "Customer"
            plan_name = sub.plan.name if sub.plan else "Standard"
            price = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
            total_amount += price
            items.append(
                DrillDownItemResponse(
                    id=str(sub.id),
                    entity_type="subscription",
                    reference_number=sub.subscription_number,
                    customer_name=cust,
                    customer_account_id=sub.customer_account_id,
                    plan_name=plan_name,
                    date=sub.start_date,
                    metric_category="Active Subscriptions",
                    status=sub.status.value,
                    currency=sub.customer_account.currency if sub.customer_account else "USD",
                    amount=price,
                    paid_amount=Decimal("0.00"),
                    balance=Decimal("0.00"),
                )
            )

    else:
        # Default: Invoiced Revenue, Outstanding, Overdue, or All Invoices
        query = (
            select(Invoice)
            .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
            .outerjoin(Subscription, Invoice.subscription_id == Subscription.id)
            .options(
                selectinload(Invoice.customer_account),
                selectinload(Invoice.subscription).selectinload(Subscription.plan),
            )
            .order_by(Invoice.issue_date.desc())
        )

        filters = []
        if m in ("invoiced", "revenue"):
            filters.append(Invoice.issue_date >= p_start)
            filters.append(Invoice.issue_date <= p_end)
            filters.append(Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.PAID]))
        elif m == "outstanding":
            filters.append(Invoice.status == InvoiceStatus.CONFIRMED)
            filters.append((Invoice.total_amount - Invoice.paid_amount) > Decimal("0.00"))
        elif m == "overdue":
            filters.append(Invoice.status == InvoiceStatus.CONFIRMED)
            filters.append(Invoice.due_date < today)
            filters.append((Invoice.total_amount - Invoice.paid_amount) > Decimal("0.00"))

        if customer_account_id:
            filters.append(Invoice.customer_account_id == customer_account_id)
        if plan_id:
            filters.append(Subscription.plan_id == plan_id)
        if status and status.strip():
            try:
                filters.append(Invoice.status == InvoiceStatus(status.lower().strip()))
            except ValueError:
                pass
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Invoice.invoice_number.ilike(term),
                    CustomerAccount.company_name.ilike(term),
                )
            )

        if filters:
            query = query.where(*filters)

        invoices = (await db.execute(query)).scalars().all()
        for inv in invoices:
            cust = inv.customer_account.company_name if inv.customer_account else (inv.customer_snapshot or {}).get("company_name", "Customer")
            plan_name = inv.subscription.plan.name if inv.subscription and inv.subscription.plan else "Custom"
            balance = max(Decimal("0.00"), inv.total_amount - inv.paid_amount)
            total_amount += inv.total_amount
            category = "Overdue Invoices" if inv.due_date < today and balance > 0 else "Invoiced Revenue"
            items.append(
                DrillDownItemResponse(
                    id=str(inv.id),
                    entity_type="invoice",
                    reference_number=inv.invoice_number,
                    customer_name=cust,
                    customer_account_id=inv.customer_account_id,
                    plan_name=plan_name,
                    date=inv.issue_date,
                    metric_category=category,
                    status=inv.status.value,
                    currency=inv.currency,
                    amount=inv.total_amount,
                    paid_amount=inv.paid_amount,
                    balance=balance,
                )
            )

    total_items = len(items)
    total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
    start_idx = (page - 1) * page_size
    paged_items = items[start_idx : start_idx + page_size]

    return DrillDownResponse(
        metric=m,
        period_start=p_start,
        period_end=p_end,
        total_items=total_items,
        total_amount=total_amount,
        items=paged_items,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/export", tags=["Reports"])
async def export_finance_report(
    metric: str = Query("invoiced", description="invoiced, collected, outstanding, overdue, subscriptions, all"),
    period: Optional[str] = Query("this_month"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    plan_id: Optional[uuid.UUID] = Query(None),
    customer_account_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    """
    Export Finance Dataset as a structured CSV spreadsheet for audit and month-end reconciliation.
    """
    # Reuse drill-down extraction logic with large page size to fetch entire dataset
    drill_data = await get_drill_down_report(
        metric=metric,
        period=period,
        start_date=start_date,
        end_date=end_date,
        plan_id=plan_id,
        customer_account_id=customer_account_id,
        status=status,
        search=search,
        page=1,
        page_size=5000,
        db=db,
        _user=_user,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Reference Number",
        "Entity Type",
        "Customer Name",
        "Plan",
        "Date",
        "Category",
        "Status",
        "Currency",
        "Amount",
        "Paid Amount",
        "Outstanding Balance",
    ])

    for row in drill_data.items:
        writer.writerow([
            row.reference_number,
            row.entity_type,
            row.customer_name,
            row.plan_name or "Standard",
            row.date.isoformat(),
            row.metric_category,
            row.status,
            row.currency,
            f"{row.amount:.2f}",
            f"{row.paid_amount:.2f}" if row.paid_amount is not None else "0.00",
            f"{row.balance:.2f}" if row.balance is not None else "0.00",
        ])

    csv_content = output.getvalue()
    today_str = organization_today().isoformat()
    filename = f"brightloop_finance_{metric}_{today_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
