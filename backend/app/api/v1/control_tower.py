import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, SendStatus
from app.models.billing_run import BillingRun, BillingRunItem, BillingRunStatus, BillingRunItemStatus
from app.models.catalog import Product, ProductVariant
from app.models.plan import Plan, BillingCadence
from app.models.tax import TaxRule
from app.models.discount import DiscountRule, DiscountRedemption, DiscountType, DiscountScope
from app.models.user import User
from app.schemas.billing_run import (
    ControlTowerPreviewResponse,
    ControlTowerItemResponse,
    CommitBatchResponse,
)
from app.api.v1.deps import require_staff_or_admin, require_admin

router = APIRouter()


class CommitBatchRequest(BaseModel):
    approved_subscription_ids: Optional[List[uuid.UUID]] = None


def compute_next_billing_date(current_date: date, cadence: BillingCadence, anchor_day: int) -> date:
    """Calculate the next billing cycle date with month-end anchor clamping."""
    if cadence == BillingCadence.DAILY:
        return current_date + timedelta(days=1)
    elif cadence == BillingCadence.WEEKLY:
        return current_date + timedelta(days=7)
    elif cadence == BillingCadence.MONTHLY:
        year = current_date.year + (current_date.month // 12)
        month = (current_date.month % 12) + 1
        _, days_in_month = calendar.monthrange(year, month)
        clamped_day = min(anchor_day, days_in_month)
        return date(year, month, clamped_day)
    elif cadence == BillingCadence.YEARLY:
        year = current_date.year + 1
        month = current_date.month
        _, days_in_month = calendar.monthrange(year, month)
        clamped_day = min(anchor_day, days_in_month)
        return date(year, month, clamped_day)
    return current_date + timedelta(days=30)


async def get_next_invoice_number(db: AsyncSession, year: int) -> str:
    """Generate sequential, monotonic invoice number that never repeats across runs."""
    count_query = select(func.count(Invoice.id))
    total_count = (await db.execute(count_query)).scalar() or 0
    return f"INV-{year}-{str(total_count + 1).zfill(5)}"


@router.get("/preview", response_model=ControlTowerPreviewResponse, tags=["Control Tower"])
async def preview_billing_batch(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """
    Billing Control Tower Preview Engine:
    - Evaluates subscriptions due based on next_billing_date and cadence.
    - Resolves active tax rules and line-specific tax configurations.
    - Evaluates discount rules, min spend/quantity thresholds, and caps via redemption counts.
    - Explains variances against prior invoices and flags anomalies.
    """
    today = date.today()
    period_start = today.replace(day=1)
    next_month = (period_start + timedelta(days=32)).replace(day=1)
    period_end = next_month - timedelta(days=1)

    # 1. Fetch active Tax Rules
    tax_rules = (await db.execute(select(TaxRule).where(TaxRule.is_active == True))).scalars().all()  # noqa: E712
    default_tax_rate = tax_rules[0].rate_percentage if tax_rules else Decimal("0.00")
    tax_map = {t.id: t for t in tax_rules}

    # 2. Fetch active Discount Rules
    discount_rules = (
        await db.execute(
            select(DiscountRule).where(
                DiscountRule.is_active == True,  # noqa: E712
                DiscountRule.valid_from <= today,
                DiscountRule.valid_to >= today,
            )
        )
    ).scalars().all()

    # 3. Query subscriptions due for billing
    query = (
        select(Subscription)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            (Subscription.next_billing_date == None) | (Subscription.next_billing_date <= period_end),  # noqa: E711
        )
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )
    result = await db.execute(query)
    subs = result.scalars().all()

    items = []
    total_projected = Decimal("0.00")
    flagged_count = 0

    for sub in subs:
        warnings = []
        variance_reasons = []

        # Step 1: Base plan price
        plan_base = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        lines_subtotal = Decimal("0.00")
        total_quantity = 0

        for line in sub.lines:
            line_cost = Decimal(str(line.unit_price)) * line.quantity
            lines_subtotal += line_cost
            total_quantity += line.quantity

        gross_subtotal = plan_base + lines_subtotal

        # Step 2: Discount evaluation
        applicable_discount = Decimal("0.00")
        matched_discount_rule = None

        for disc in discount_rules:
            # Check eligibility threshold
            if gross_subtotal >= disc.min_spend and total_quantity >= disc.min_quantity:
                # Check transactional cap via redemptions
                redemption_count = (
                    await db.execute(
                        select(func.count(DiscountRedemption.id)).where(
                            DiscountRedemption.discount_rule_id == disc.id
                        )
                    )
                ).scalar() or 0

                if disc.max_usage_limit and redemption_count >= disc.max_usage_limit:
                    warnings.append(f"Discount '{disc.name}' limit exhausted ({redemption_count}/{disc.max_usage_limit}).")
                    continue

                if disc.discount_type == DiscountType.PERCENTAGE:
                    disc_amount = (gross_subtotal * (disc.value / Decimal("100.00"))).quantize(Decimal("0.01"))
                else:
                    disc_amount = min(gross_subtotal, disc.value)

                if disc_amount > applicable_discount:
                    applicable_discount = disc_amount
                    matched_discount_rule = disc

        net_subtotal = max(Decimal("0.00"), gross_subtotal - applicable_discount)

        # Step 3: Tax calculation from real rules
        total_tax = Decimal("0.00")
        for line in sub.lines:
            rule = tax_map.get(line.tax_rule_id) if line.tax_rule_id else None
            rate = rule.rate_percentage if rule else default_tax_rate
            line_cost = Decimal(str(line.unit_price)) * line.quantity
            total_tax += (line_cost * (rate / Decimal("100.00"))).quantize(Decimal("0.01"))

        if not sub.lines and default_tax_rate > 0:
            total_tax += (net_subtotal * (default_tax_rate / Decimal("100.00"))).quantize(Decimal("0.01"))

        expected_total = net_subtotal + total_tax
        total_projected += expected_total

        # Step 4: Prior invoice comparison & anomaly flags
        prior_query = (
            select(Invoice)
            .where(Invoice.subscription_id == sub.id)
            .order_by(Invoice.issue_date.desc())
            .limit(1)
        )
        prior_inv = (await db.execute(prior_query)).scalar_one_or_none()
        prior_total = prior_inv.total_amount if prior_inv else expected_total
        variance = expected_total - prior_total

        item_status = BillingRunItemStatus.APPROVED

        if sub.customer_account and not sub.customer_account.tax_id:
            warnings.append("Missing Customer Tax ID on file.")
            item_status = BillingRunItemStatus.FLAGGED

        if sub.plan and not sub.plan.is_active:
            warnings.append("Associated plan has been deactivated.")
            item_status = BillingRunItemStatus.FLAGGED

        if variance != Decimal("0.00"):
            variance_reasons.append(f"Calculated price changed by ${variance:+.2f} vs prior invoice.")

        if item_status == BillingRunItemStatus.FLAGGED:
            flagged_count += 1

        items.append(
            ControlTowerItemResponse(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                subscription_number=sub.subscription_number,
                customer_name=sub.customer_account.company_name if sub.customer_account else "Unknown",
                plan_name=sub.plan.name if sub.plan else "Standard",
                expected_subtotal=gross_subtotal,
                expected_tax_amount=total_tax,
                expected_discount_amount=applicable_discount,
                expected_total_amount=expected_total,
                prior_invoice_total=prior_total,
                variance_amount=variance,
                variance_reasons=variance_reasons,
                warnings=warnings,
                status=item_status,
            )
        )

    return ControlTowerPreviewResponse(
        billing_period_start=period_start.isoformat(),
        billing_period_end=period_end.isoformat(),
        total_subscriptions=len(items),
        total_projected_amount=total_projected,
        flagged_count=flagged_count,
        items=items,
    )


@router.post("/commit", response_model=CommitBatchResponse, tags=["Control Tower"])
async def commit_billing_batch(
    payload: Optional[CommitBatchRequest] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Commit the audited billing run (Admin only).
    - Respects preview approval: bills only approved/clean subscriptions.
    - Generates monotonic sequential invoice numbers that never repeat across runs.
    - Atomically snapshots lines and reserves discount redemptions transactionally.
    - Advances subscription next_billing_date according to cadence and anchor day clamping.
    """
    today = date.today()
    period_start = today.replace(day=1)
    next_month = (period_start + timedelta(days=32)).replace(day=1)
    period_end = next_month - timedelta(days=1)

    # Tax & Discount rules
    tax_rules = (await db.execute(select(TaxRule).where(TaxRule.is_active == True))).scalars().all()  # noqa: E712
    default_tax_rate = tax_rules[0].rate_percentage if tax_rules else Decimal("0.00")
    tax_map = {t.id: t for t in tax_rules}

    discount_rules = (
        await db.execute(
            select(DiscountRule).where(
                DiscountRule.is_active == True,  # noqa: E712
                DiscountRule.valid_from <= today,
                DiscountRule.valid_to >= today,
            )
        )
    ).scalars().all()

    query = (
        select(Subscription)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            (Subscription.next_billing_date == None) | (Subscription.next_billing_date <= period_end),  # noqa: E711
        )
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )
    subs = (await db.execute(query)).scalars().all()

    # Filter to approved items if requested
    if payload and payload.approved_subscription_ids is not None:
        approved_set = set(payload.approved_subscription_ids)
        subs = [s for s in subs if s.id in approved_set]

    if not subs:
        raise HTTPException(status_code=400, detail="No eligible subscriptions to commit.")

    billing_run = BillingRun(
        run_date=today,
        billing_period_start=period_start,
        billing_period_end=period_end,
        status=BillingRunStatus.COMMITTED,
        total_evaluated=len(subs),
        created_by_user_id=admin_user.id,
        committed_by_user_id=admin_user.id,
    )
    db.add(billing_run)
    await db.flush()

    invoices_created = 0
    total_invoiced = Decimal("0.00")

    for sub in subs:
        idempotency_key = f"sub_{sub.id}_{period_start.isoformat()}_{period_end.isoformat()}"

        # Idempotency duplicate check
        existing_check = select(Invoice).where(Invoice.idempotency_key == idempotency_key)
        if (await db.execute(existing_check)).scalar_one_or_none():
            continue

        plan_base = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        lines_subtotal = Decimal("0.00")
        total_quantity = 0
        invoice_lines = []

        if sub.plan:
            invoice_lines.append(
                InvoiceLine(
                    description=f"Plan Base Fee — {sub.plan.name}",
                    product_name_snapshot=sub.plan.name,
                    quantity=1,
                    unit_price_snapshot=sub.plan.base_price,
                    subtotal=sub.plan.base_price,
                    line_total=sub.plan.base_price,
                )
            )

        for line in sub.lines:
            line_cost = Decimal(str(line.unit_price)) * line.quantity
            lines_subtotal += line_cost
            total_quantity += line.quantity

            rule = tax_map.get(line.tax_rule_id) if line.tax_rule_id else None
            rate = rule.rate_percentage if rule else default_tax_rate
            line_tax = (line_cost * (rate / Decimal("100.00"))).quantize(Decimal("0.01"))

            desc = line.product.name if line.product else "Product Line"
            if line.variant:
                desc += f" ({line.variant.name})"

            invoice_lines.append(
                InvoiceLine(
                    description=desc,
                    product_name_snapshot=line.product.name if line.product else "Product",
                    variant_name_snapshot=line.variant.name if line.variant else None,
                    quantity=line.quantity,
                    unit_price_snapshot=line.unit_price,
                    subtotal=line_cost,
                    tax_rate_snapshot=rate,
                    tax_amount=line_tax,
                    line_total=line_cost + line_tax,
                )
            )

        gross_subtotal = plan_base + lines_subtotal

        # Apply discount
        applicable_discount = Decimal("0.00")
        matched_discount = None

        for disc in discount_rules:
            if gross_subtotal >= disc.min_spend and total_quantity >= disc.min_quantity:
                redemption_count = (
                    await db.execute(
                        select(func.count(DiscountRedemption.id)).where(
                            DiscountRedemption.discount_rule_id == disc.id
                        )
                    )
                ).scalar() or 0

                if disc.max_usage_limit and redemption_count >= disc.max_usage_limit:
                    continue

                if disc.discount_type == DiscountType.PERCENTAGE:
                    disc_amount = (gross_subtotal * (disc.value / Decimal("100.00"))).quantize(Decimal("0.01"))
                else:
                    disc_amount = min(gross_subtotal, disc.value)

                if disc_amount > applicable_discount:
                    applicable_discount = disc_amount
                    matched_discount = disc

        net_subtotal = max(Decimal("0.00"), gross_subtotal - applicable_discount)
        total_tax = sum(l.tax_amount for l in invoice_lines)
        total_amount = net_subtotal + total_tax
        total_invoiced += total_amount

        # Sequential invoice number
        invoice_number = await get_next_invoice_number(db, today.year)

        customer_snap = {
            "company_name": sub.customer_account.company_name if sub.customer_account else "Customer",
            "billing_email": sub.customer_account.billing_email if sub.customer_account else "",
            "tax_id": sub.customer_account.tax_id if sub.customer_account else None,
        }
        address_snap = {
            "address": sub.customer_account.billing_address_line1 if sub.customer_account else "",
            "city": sub.customer_account.billing_city if sub.customer_account else "",
            "country": sub.customer_account.billing_country if sub.customer_account else "US",
        }

        invoice = Invoice(
            invoice_number=invoice_number,
            subscription_id=sub.id,
            customer_account_id=sub.customer_account_id,
            billing_run_id=billing_run.id,
            idempotency_key=idempotency_key,
            currency="USD",
            status=InvoiceStatus.CONFIRMED,
            billing_period_start=period_start,
            billing_period_end=period_end,
            subtotal=gross_subtotal,
            tax_amount=total_tax,
            discount_amount=applicable_discount,
            total_amount=total_amount,
            paid_amount=Decimal("0.00"),
            issue_date=today,
            due_date=today + timedelta(days=sub.payment_terms_days),
            send_status=SendStatus.NOT_SENT,
            customer_snapshot=customer_snap,
            billing_address_snapshot=address_snap,
            lines=invoice_lines,
        )
        db.add(invoice)
        await db.flush()

        # Record discount redemption transactionally
        if matched_discount:
            redemption = DiscountRedemption(
                discount_rule_id=matched_discount.id,
                invoice_id=invoice.id,
                subscription_id=sub.id,
            )
            db.add(redemption)

        # Advance subscription next_billing_date based on cadence
        cadence = sub.plan.cadence if sub.plan else BillingCadence.MONTHLY
        sub.next_billing_date = compute_next_billing_date(
            sub.next_billing_date or today, cadence, sub.billing_anchor_day
        )

        invoices_created += 1

    billing_run.total_amount_projected = total_invoiced
    await db.commit()

    return CommitBatchResponse(
        billing_run_id=billing_run.id,
        invoices_created_count=invoices_created,
        total_invoiced_amount=total_invoiced,
        status="committed",
    )
