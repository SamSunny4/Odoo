import csv
import io
import uuid
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_staff_or_admin, require_admin
from app.core.clock import organization_today
from app.core.config import settings
from app.core.database import get_db
from app.models.customer import CustomerAccount
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentReversal
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
    if start_date or end_date:
        if not start_date or not end_date:
            raise HTTPException(status_code=422, detail="Both start_date and end_date are required for a custom period.")
        if start_date > end_date:
            raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
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
    elif p == "this_month":
        p_start = today.replace(day=1)
        p_end = today
        return p_start, p_end, "this_month"
    elif p == "custom":
        raise HTTPException(status_code=422, detail="Custom period requires start_date and end_date.")
    raise HTTPException(status_code=422, detail="Unsupported reporting period.")


async def _normalized_mrr_by_subscription(
    db: AsyncSession,
    subscriptions: list[Subscription],
    as_of: date,
) -> dict[uuid.UUID, Decimal]:
    """Calculate each subscription's contribution using the same rules as dashboard MRR."""
    tax_map, default_tax_rule, discount_rules, redemption_counts = await _load_pricing_rules(db)
    mrr_by_subscription: dict[uuid.UUID, Decimal] = {}
    for subscription in subscriptions:
        if subscription.customer_account and subscription.customer_account.currency != settings.ORGANIZATION_CURRENCY:
            continue
        charge = calculate_subscription_charge(
            subscription,
            tax_map=tax_map,
            default_tax_rule=default_tax_rule,
            discount_rules=discount_rules,
            redemption_counts=redemption_counts,
            as_of=as_of,
        )
        amount = max(Decimal("0.00"), charge.subtotal - charge.discount)
        cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
        if cadence == BillingCadence.DAILY:
            amount *= Decimal("30")
        elif cadence == BillingCadence.WEEKLY:
            amount *= Decimal("52") / Decimal("12")
        elif cadence == BillingCadence.YEARLY:
            amount /= Decimal("12")
        mrr_by_subscription[subscription.id] = amount.quantize(CENT, rounding=ROUND_HALF_UP)
        if charge.discount_rule and not charge.warnings:
            redemption_counts[charge.discount_rule.id] = redemption_counts.get(charge.discount_rule.id, 0) + 1
    return mrr_by_subscription


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
        mrr_by_subscription = await _normalized_mrr_by_subscription(db, active_subscriptions, today)
        monthly_run_rate = sum(mrr_by_subscription.values(), Decimal("0.00"))

    overdue_rows = (await db.execute(
        select(Invoice.total_amount, Invoice.paid_amount)
        .where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < today,
            Invoice.paid_amount < Invoice.total_amount,
            Invoice.currency == settings.ORGANIZATION_CURRENCY,
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

        reversal_totals = (
            select(
                PaymentReversal.payment_id.label("payment_id"),
                func.sum(PaymentReversal.reversal_amount).label("reversed_amount"),
            )
            .group_by(PaymentReversal.payment_id)
            .subquery()
        )
        # Cash collected within the date range, net of every partial or full reversal.
        cash_collected = await db.scalar(
            select(func.coalesce(
                func.sum(Payment.amount - func.coalesce(reversal_totals.c.reversed_amount, 0)),
                0,
            ))
            .select_from(Payment)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(reversal_totals, reversal_totals.c.payment_id == Payment.id)
            .where(
                Payment.payment_date >= p_start,
                Payment.payment_date <= p_end,
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
    aliases = {"cash_collected": "collected", "revenue": "invoiced", "mrr": "subscriptions"}
    m = aliases.get(metric.lower().strip(), metric.lower().strip())
    if m not in {"invoiced", "collected", "outstanding", "overdue", "subscriptions", "all"}:
        raise HTTPException(status_code=422, detail="Unsupported drill-down metric.")

    total_amount = Decimal("0.00")
    total_items = 0
    paged_items: list[DrillDownItemResponse] = []

    if m == "collected":
        reversal_totals = (
            select(
                PaymentReversal.payment_id.label("payment_id"),
                func.sum(PaymentReversal.reversal_amount).label("reversed_amount"),
            )
            .group_by(PaymentReversal.payment_id)
            .subquery()
        )
        reversed_amount = func.coalesce(reversal_totals.c.reversed_amount, 0)
        net_amount = Payment.amount - reversed_amount
        filters = [
            Payment.payment_date >= p_start,
            Payment.payment_date <= p_end,
            Invoice.currency == settings.ORGANIZATION_CURRENCY,
        ]
        if customer_account_id:
            filters.append(Invoice.customer_account_id == customer_account_id)
        if plan_id:
            filters.append(Subscription.plan_id == plan_id)
        if status and status.strip():
            state = status.strip().lower()
            if state == "settled":
                filters.append(reversed_amount == 0)
            elif state == "partially_refunded":
                filters.extend([reversed_amount > 0, net_amount > 0])
            elif state == "reversed":
                filters.append(net_amount <= 0)
            else:
                raise HTTPException(status_code=422, detail="Payment status must be settled, partially_refunded, or reversed.")
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(
                Invoice.invoice_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
                Payment.reference_note.ilike(term),
            ))

        def payment_statement(statement):
            statement = (
                statement.select_from(Payment)
                .join(Invoice, Invoice.id == Payment.invoice_id)
                .outerjoin(CustomerAccount, CustomerAccount.id == Invoice.customer_account_id)
                .outerjoin(reversal_totals, reversal_totals.c.payment_id == Payment.id)
            )
            if plan_id:
                statement = statement.join(Subscription, Subscription.id == Invoice.subscription_id)
            return statement.where(*filters)

        total_items = await db.scalar(payment_statement(select(func.count(Payment.id)))) or 0
        total_amount = await db.scalar(
            payment_statement(select(func.coalesce(func.sum(net_amount), 0)))
        ) or Decimal("0.00")
        rows = (await db.execute(
            payment_statement(
                select(Payment, reversed_amount.label("reversed_amount"))
                .options(
                    selectinload(Payment.invoice).selectinload(Invoice.customer_account),
                    selectinload(Payment.invoice).selectinload(Invoice.subscription).selectinload(Subscription.plan),
                    selectinload(Payment.reversals),
                )
                .order_by(Payment.payment_date.desc(), Payment.created_at.desc(), Payment.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )).all()
        for payment, reversed_total in rows:
            invoice = payment.invoice
            balance = max(Decimal("0.00"), Decimal(str(payment.amount)) - Decimal(str(reversed_total or 0)))
            reversal_amount = Decimal(str(reversed_total or 0))
            state = "Reversed" if balance == 0 else "Partially Refunded" if reversal_amount > 0 else "Settled"
            paged_items.append(DrillDownItemResponse(
                id=str(payment.id),
                entity_type="payment",
                reference_number=f"PAY-{invoice.invoice_number}",
                customer_name=invoice.customer_account.company_name if invoice.customer_account else (invoice.customer_snapshot or {}).get("company_name", "Customer"),
                customer_account_id=invoice.customer_account_id,
                plan_name=invoice.subscription.plan.name if invoice.subscription and invoice.subscription.plan else "Remittance",
                date=payment.payment_date,
                metric_category="Cash Collections",
                status=state,
                currency=invoice.currency,
                amount=balance,
                paid_amount=balance,
                balance=Decimal("0.00"),
            ))

    elif m == "subscriptions":
        filters = [Subscription.status == SubscriptionStatus.ACTIVE]
        if plan_id:
            filters.append(Subscription.plan_id == plan_id)
        if customer_account_id:
            filters.append(Subscription.customer_account_id == customer_account_id)
        if status and status.strip():
            try:
                filters.append(Subscription.status == SubscriptionStatus(status.strip().lower()))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Unsupported subscription status.") from exc
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(
                Subscription.subscription_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
            ))
        query = (
            select(Subscription)
            .join(CustomerAccount, CustomerAccount.id == Subscription.customer_account_id)
            .where(*filters, CustomerAccount.currency == settings.ORGANIZATION_CURRENCY)
            .options(*_subscription_options())
            .order_by(func.coalesce(Subscription.next_billing_date, Subscription.start_date), Subscription.subscription_number)
        )
        subscriptions = (await db.execute(query)).scalars().all()
        mrr_by_subscription = await _normalized_mrr_by_subscription(db, subscriptions, today)
        total_items = len(mrr_by_subscription)
        total_amount = sum(mrr_by_subscription.values(), Decimal("0.00"))
        for subscription in subscriptions[(page - 1) * page_size : page * page_size]:
            if subscription.id not in mrr_by_subscription:
                continue
            paged_items.append(DrillDownItemResponse(
                id=str(subscription.id),
                entity_type="subscription",
                reference_number=subscription.subscription_number,
                customer_name=subscription.customer_account.company_name if subscription.customer_account else "Customer",
                customer_account_id=subscription.customer_account_id,
                plan_name=subscription.plan.name if subscription.plan else "Standard",
                date=subscription.start_date,
                metric_category="Monthly Recurring Revenue",
                status=subscription.status.value,
                currency=settings.ORGANIZATION_CURRENCY,
                amount=mrr_by_subscription[subscription.id],
                paid_amount=Decimal("0.00"),
                balance=Decimal("0.00"),
            ))

    else:
        filters = [Invoice.currency == settings.ORGANIZATION_CURRENCY]
        if m == "invoiced":
            filters.extend([
                Invoice.issue_date >= p_start,
                Invoice.issue_date <= p_end,
                Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.PAID]),
            ])
        elif m == "outstanding":
            filters.extend([
                Invoice.status == InvoiceStatus.CONFIRMED,
                (Invoice.total_amount - Invoice.paid_amount) > Decimal("0.00"),
            ])
        elif m == "overdue":
            filters.extend([
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.due_date < today,
                (Invoice.total_amount - Invoice.paid_amount) > Decimal("0.00"),
            ])
        elif m == "all":
            filters.extend([Invoice.issue_date >= p_start, Invoice.issue_date <= p_end])
        if customer_account_id:
            filters.append(Invoice.customer_account_id == customer_account_id)
        if plan_id:
            filters.append(Subscription.plan_id == plan_id)
        if status and status.strip():
            try:
                filters.append(Invoice.status == InvoiceStatus(status.strip().lower()))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="Unsupported invoice status.") from exc
        if search and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(
                Invoice.invoice_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
            ))

        def invoice_statement(statement):
            return (
                statement.select_from(Invoice)
                .outerjoin(CustomerAccount, CustomerAccount.id == Invoice.customer_account_id)
                .outerjoin(Subscription, Subscription.id == Invoice.subscription_id)
                .where(*filters)
            )

        total_items = await db.scalar(invoice_statement(select(func.count(Invoice.id)))) or 0
        metric_amount = (
            Invoice.total_amount - Invoice.paid_amount
            if m in {"outstanding", "overdue"}
            else Invoice.total_amount
        )
        total_amount = await db.scalar(
            invoice_statement(select(func.coalesce(func.sum(metric_amount), 0)))
        ) or Decimal("0.00")
        invoices = (await db.execute(
            invoice_statement(
                select(Invoice)
                .options(
                    selectinload(Invoice.customer_account),
                    selectinload(Invoice.subscription).selectinload(Subscription.plan),
                )
                .order_by(Invoice.issue_date.desc(), Invoice.invoice_number.desc(), Invoice.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )).scalars().all()
        for invoice in invoices:
            balance = max(Decimal("0.00"), invoice.total_amount - invoice.paid_amount)
            category = "Overdue Invoices" if invoice.due_date < today and balance > 0 else "Invoiced Revenue"
            paged_items.append(DrillDownItemResponse(
                id=str(invoice.id),
                entity_type="invoice",
                reference_number=invoice.invoice_number,
                customer_name=invoice.customer_account.company_name if invoice.customer_account else (invoice.customer_snapshot or {}).get("company_name", "Customer"),
                customer_account_id=invoice.customer_account_id,
                plan_name=invoice.subscription.plan.name if invoice.subscription and invoice.subscription.plan else "Custom",
                date=invoice.issue_date,
                metric_category=category,
                status=invoice.status.value,
                currency=invoice.currency,
                amount=invoice.total_amount,
                paid_amount=invoice.paid_amount,
                balance=balance,
            ))

    total_pages = (total_items + page_size - 1) // page_size if total_items else 1
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

    page = 1
    drill_data = await get_drill_down_report(
        metric=metric,
        period=period,
        start_date=start_date,
        end_date=end_date,
        plan_id=plan_id,
        customer_account_id=customer_account_id,
        status=status,
        search=search,
        page=page,
        page_size=100,
        db=db,
        _user=_user,
    )
    if drill_data.metric == "subscriptions" and drill_data.total_items > drill_data.page_size:
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
            page_size=drill_data.total_items,
            db=db,
            _user=_user,
        )
    while True:
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
        if page >= drill_data.total_pages:
            break
        page += 1
        drill_data = await get_drill_down_report(
            metric=metric,
            period=period,
            start_date=start_date,
            end_date=end_date,
            plan_id=plan_id,
            customer_account_id=customer_account_id,
            status=status,
            search=search,
            page=page,
            page_size=100,
            db=db,
            _user=_user,
        )

    csv_content = output.getvalue()
    today_str = organization_today().isoformat()
    filename = f"brightloop_finance_{metric}_{today_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
