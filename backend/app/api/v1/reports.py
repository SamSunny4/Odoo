from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_staff_or_admin
from app.core.clock import organization_today
from app.core.config import settings
from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.plan import BillingCadence
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.schemas.report import DashboardSummaryResponse
from app.services.billing import _load_pricing_rules, _subscription_options, calculate_subscription_charge

router = APIRouter()
CENT = Decimal("0.01")


@router.get("/summary", response_model=DashboardSummaryResponse, tags=["Reports"])
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    today = organization_today()
    month_start = today.replace(day=1)
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

    financial: dict[str, Decimal | None] = {
        "monthly_recurring_revenue": None,
        "invoiced_mtd": None,
        "cash_collected_mtd": None,
        "outstanding_balance": None,
        "overdue_balance": None,
    }
    if user.role == UserRole.ADMIN:
        financial["monthly_recurring_revenue"] = monthly_run_rate.quantize(CENT, rounding=ROUND_HALF_UP)
        financial["invoiced_mtd"] = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount), 0)).where(
                Invoice.issue_date >= month_start,
                Invoice.issue_date <= today,
                Invoice.status.in_([InvoiceStatus.CONFIRMED, InvoiceStatus.PAID]),
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )
        financial["cash_collected_mtd"] = await db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0))
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .where(
                Payment.payment_date >= month_start,
                Payment.payment_date <= today,
                Payment.is_reversed.is_(False),
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )
        financial["outstanding_balance"] = await db.scalar(
            select(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0)).where(
                Invoice.status == InvoiceStatus.CONFIRMED,
                Invoice.total_amount > Invoice.paid_amount,
                Invoice.currency == settings.ORGANIZATION_CURRENCY,
            )
        )
        financial["overdue_balance"] = overdue_balance

    return DashboardSummaryResponse(
        currency=settings.ORGANIZATION_CURRENCY,
        active_subscription_count=active_subscription_count or 0,
        monthly_recurring_revenue=financial["monthly_recurring_revenue"],
        invoiced_mtd=financial["invoiced_mtd"],
        cash_collected_mtd=financial["cash_collected_mtd"],
        outstanding_balance=financial["outstanding_balance"],
        overdue_balance=financial["overdue_balance"],
        overdue_invoice_count=overdue_count or 0,
        pending_quotes_count=pending_quotes or 0,
        renewals_due_7d_count=renewals_due or 0,
    )
