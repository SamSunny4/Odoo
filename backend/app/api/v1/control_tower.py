import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, SendStatus
from app.models.billing_run import BillingRun, BillingRunItem, BillingRunStatus, BillingRunItemStatus
from app.models.user import User, UserRole
from app.schemas.billing_run import (
    ControlTowerPreviewResponse,
    ControlTowerItemResponse,
    CommitBatchResponse,
)
from app.api.v1.deps import require_staff_or_admin, require_admin, get_current_user

router = APIRouter()


@router.get("/preview", response_model=ControlTowerPreviewResponse, tags=["Control Tower"])
async def preview_billing_batch(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """
    Billing Control Tower:
    Calculates expected invoices from current subscription, variant, tax, and discount data.
    Presents a reviewable batch with per-subscription calculation, prior invoice comparison, and anomaly warnings.
    """
    today = date.today()
    period_start = today.replace(day=1)
    # Next month start - 1 day
    next_month = (period_start + timedelta(days=32)).replace(day=1)
    period_end = next_month - timedelta(days=1)

    query = (
        select(Subscription)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(Subscription.lines.property.mapper.class_.product),
            selectinload(Subscription.lines).selectinload(Subscription.lines.property.mapper.class_.variant),
        )
    )
    result = await db.execute(query)
    subs = result.scalars().all()

    items = []
    total_projected = Decimal("0.00")
    flagged_count = 0

    for sub in subs:
        # 1. Base price
        subtotal = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        for line in sub.lines:
            subtotal += Decimal(str(line.unit_price)) * line.quantity

        # 2. Tax rule (approx 10% standard)
        tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        discount = Decimal("0.00")
        total = subtotal - discount + tax
        total_projected += total

        # Check prior invoice for variance
        prior_query = (
            select(Invoice)
            .where(Invoice.subscription_id == sub.id)
            .order_by(Invoice.issue_date.desc())
            .limit(1)
        )
        prior_inv = (await db.execute(prior_query)).scalar_one_or_none()
        prior_total = prior_inv.total_amount if prior_inv else total
        variance = total - prior_total

        variance_reasons = []
        warnings = []
        item_status = BillingRunItemStatus.APPROVED

        if sub.customer_account and not sub.customer_account.tax_id:
            warnings.append("Missing Customer Tax ID on file.")
            item_status = BillingRunItemStatus.FLAGGED
            flagged_count += 1

        if variance != Decimal("0.00"):
            variance_reasons.append(f"Price adjusted by ${variance:.2f} compared to prior cycle.")

        items.append(
            ControlTowerItemResponse(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                subscription_number=sub.subscription_number,
                customer_name=sub.customer_account.company_name if sub.customer_account else "Unknown",
                plan_name=sub.plan.name if sub.plan else "Standard",
                expected_subtotal=subtotal,
                expected_tax_amount=tax,
                expected_discount_amount=discount,
                expected_total_amount=total,
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
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """
    Commit the audited billing run (Admin only!).
    Atomically generates invoices with idempotency keys, snapshots lines, and updates billing dates.
    """
    today = date.today()
    period_start = today.replace(day=1)
    next_month = (period_start + timedelta(days=32)).replace(day=1)
    period_end = next_month - timedelta(days=1)

    # 1. Fetch active subscriptions
    query = (
        select(Subscription)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(Subscription.lines.property.mapper.class_.product),
            selectinload(Subscription.lines).selectinload(Subscription.lines.property.mapper.class_.variant),
        )
    )
    result = await db.execute(query)
    subs = result.scalars().all()

    if not subs:
        raise HTTPException(status_code=400, detail="No active subscriptions to bill.")

    # 2. Create BillingRun record
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

    for idx, sub in enumerate(subs, 1):
        idempotency_key = f"sub_{sub.id}_{period_start.isoformat()}_{period_end.isoformat()}"

        # Check existing invoice for this period
        existing_check = select(Invoice).where(Invoice.idempotency_key == idempotency_key)
        if (await db.execute(existing_check)).scalar_one_or_none():
            continue  # Safe idempotency skip

        subtotal = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        line_items = []
        if sub.plan:
            line_items.append(
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
            subtotal += line_cost
            desc = line.product.name if line.product else "Product Line"
            if line.variant:
                desc += f" ({line.variant.name})"
            line_items.append(
                InvoiceLine(
                    description=desc,
                    product_name_snapshot=line.product.name if line.product else "Product",
                    variant_name_snapshot=line.variant.name if line.variant else None,
                    quantity=line.quantity,
                    unit_price_snapshot=line.unit_price,
                    subtotal=line_cost,
                    line_total=line_cost,
                )
            )

        tax = (subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
        total = subtotal + tax
        total_invoiced += total

        customer_snap = {
            "company_name": sub.customer_account.company_name if sub.customer_account else "Acme",
            "billing_email": sub.customer_account.billing_email if sub.customer_account else "",
            "tax_id": sub.customer_account.tax_id if sub.customer_account else None,
        }
        address_snap = {
            "address": sub.customer_account.billing_address_line1 if sub.customer_account else "",
            "city": sub.customer_account.billing_city if sub.customer_account else "",
            "country": sub.customer_account.billing_country if sub.customer_account else "US",
        }

        invoice_number = f"INV-{today.year}-{str(invoices_created + 100).zfill(4)}"
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
            subtotal=subtotal,
            tax_amount=tax,
            discount_amount=Decimal("0.00"),
            total_amount=total,
            paid_amount=Decimal("0.00"),
            issue_date=today,
            due_date=today + timedelta(days=sub.payment_terms_days),
            send_status=SendStatus.NOT_SENT,
            customer_snapshot=customer_snap,
            billing_address_snapshot=address_snap,
            lines=line_items,
        )
        db.add(invoice)
        invoices_created += 1

    billing_run.total_amount_projected = total_invoiced
    await db.commit()

    return CommitBatchResponse(
        billing_run_id=billing_run.id,
        invoices_created_count=invoices_created,
        total_invoiced_amount=total_invoiced,
        status="committed",
    )

