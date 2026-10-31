"""Customer-owned subscription actions, payment history, and invoice downloads."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_customer
from app.core.clock import organization_today
from app.core.database import get_db
from app.models.catalog import Product, ProductVariant
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.payment import Payment
from app.models.plan import BillingCadence
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.user import User
from app.schemas.portal import (
    PortalAddonProductResponse,
    PortalPaymentResponse,
    PortalPaymentPage,
    PortalSubscriptionActionRequest,
    PortalSubscriptionActionResponse,
)
from app.services.audit import record_audit_event
from app.services.billing import compute_next_billing_date
from app.services.email_templates import portal_subscription_update_email
from app.services.outbox import create_outbox_message

router = APIRouter(tags=["Customer Portal"])


async def _customer_membership(user: User, db: AsyncSession) -> CustomerAccountMembership:
    membership = (await db.execute(
        select(CustomerAccountMembership).where(CustomerAccountMembership.user_id == user.id)
    )).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=403, detail="No customer account is linked to this user.")
    return membership


async def _scoped_subscription(
    db: AsyncSession,
    subscription_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    lock: bool = False,
) -> Subscription:
    query = (
        select(Subscription)
        .where(
            Subscription.id == subscription_id,
            Subscription.customer_account_id == account_id,
        )
        .options(
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )
    if lock:
        query = query.with_for_update()
    subscription = (await db.execute(query)).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    return subscription


def _renewal_end(subscription: Subscription, today: date, duration_days: int | None) -> date:
    if duration_days:
        return max(subscription.expiry_date or today, today) + timedelta(days=duration_days)
    cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
    anchor = subscription.billing_anchor_day
    current_end = subscription.expiry_date or today
    if current_end < today:
        current_end = today
    return compute_next_billing_date(current_end, cadence, anchor)


async def _notify_customer(
    db: AsyncSession,
    *,
    user: User,
    account: CustomerAccount,
    subject: str,
    body: str,
    dedupe_key: str | None = None,
) -> None:
    await create_outbox_message(
        db,
        topic="email",
        dedupe_key=dedupe_key,
        payload={"type": "portal_notification", "to": account.billing_email or user.email, "subject": subject, "body": body},
    )


@router.get("/catalog/addons", response_model=list[PortalAddonProductResponse])
async def list_customer_addons(
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
):
    """Return active products and variants only; never expose internal cost prices."""
    await _customer_membership(customer_user, db)
    products = (await db.execute(
        select(Product)
        .where(Product.is_active.is_(True), Product.is_add_on.is_(True))
        .options(selectinload(Product.variants))
        .order_by(Product.name)
    )).scalars().all()
    return [
        PortalAddonProductResponse(
            id=product.id,
            name=product.name,
            sales_price=product.sales_price,
            variants=[
                {
                    "id": variant.id,
                    "name": variant.name,
                    "price_adjustment": variant.price_adjustment,
                }
                for variant in product.variants
                if variant.is_active
            ],
        )
        for product in products
    ]


@router.post(
    "/subscriptions/{subscription_id}/actions",
    response_model=PortalSubscriptionActionResponse,
)
async def perform_customer_subscription_action(
    subscription_id: uuid.UUID,
    payload: PortalSubscriptionActionRequest,
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
):
    """Apply policy-allowed self-service changes to the signed-in customer's subscription."""
    membership = await _customer_membership(customer_user, db)
    if membership.membership_role == CustomerMembershipRole.VIEWER:
        raise HTTPException(status_code=403, detail="A billing owner or billing admin is required to change subscriptions.")
    account = (await db.execute(
        select(CustomerAccount).where(CustomerAccount.id == membership.customer_account_id)
    )).scalar_one()
    subscription = await _scoped_subscription(db, subscription_id, membership.customer_account_id, lock=True)
    plan = subscription.plan
    today = organization_today()
    action = payload.action
    old_status = subscription.status
    effective_date = today
    changes: dict = {"action": action, "reason": payload.reason}

    if action == "pause":
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Only active subscriptions can be paused.")
        if plan and not plan.allow_pause:
            raise HTTPException(status_code=409, detail="This plan does not allow pausing.")
        subscription.status = SubscriptionStatus.PAUSED

    elif action == "resume":
        if subscription.status != SubscriptionStatus.PAUSED:
            raise HTTPException(status_code=409, detail="Only paused subscriptions can be resumed.")
        if subscription.expiry_date and subscription.expiry_date < today:
            raise HTTPException(status_code=409, detail="This subscription has expired and cannot be resumed.")
        subscription.status = SubscriptionStatus.ACTIVE
        if not subscription.next_billing_date or subscription.next_billing_date < today:
            subscription.next_billing_date = today

    elif action == "cancel":
        if subscription.status == SubscriptionStatus.CLOSED:
            raise HTTPException(status_code=409, detail="This subscription is already closed.")
        if subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAUSED, SubscriptionStatus.CONFIRMED):
            if plan and not plan.allow_early_close and not subscription.expiry_date:
                raise HTTPException(status_code=409, detail="This plan requires an end date before cancellation can be scheduled.")
            if subscription.expiry_date and subscription.expiry_date > today and plan and not plan.allow_early_close:
                subscription.cancel_at_period_end = True
                effective_date = subscription.expiry_date
            else:
                subscription.status = SubscriptionStatus.CLOSED
                subscription.cancel_at_period_end = False
        else:
            subscription.status = SubscriptionStatus.CLOSED
            subscription.cancel_at_period_end = False
        changes["effective_date"] = effective_date.isoformat()
        changes["cancel_at_period_end"] = subscription.cancel_at_period_end

    elif action == "renew":
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Only active subscriptions can be renewed.")
        if plan and not plan.allow_renewal:
            raise HTTPException(status_code=409, detail="This plan does not allow renewal.")
        old_expiry = subscription.expiry_date
        effective_date = (old_expiry + timedelta(days=1)) if old_expiry and old_expiry >= today else today
        subscription.expiry_date = _renewal_end(subscription, today, payload.renewal_duration_days)
        subscription.cancel_at_period_end = False
        changes["expiry_date"] = {
            "from": old_expiry.isoformat() if old_expiry else None,
            "to": subscription.expiry_date.isoformat(),
        }

    elif action == "change_addons":
        if subscription.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="Add-ons can be changed only on active subscriptions.")
        if payload.lines is None:
            raise HTTPException(status_code=422, detail="Provide the complete desired product line list.")
        requested_keys = [(line.product_id, line.product_variant_id) for line in payload.lines]
        if len(requested_keys) != len(set(requested_keys)):
            raise HTTPException(status_code=422, detail="Each product and variant can appear only once.")
        base_lines = [line for line in subscription.lines if not (line.product and line.product.is_add_on)]
        addon_lines = [line for line in subscription.lines if line.product and line.product.is_add_on]
        existing_tax_rules = {
            (line.product_id, line.product_variant_id): line.tax_rule_id
            for line in addon_lines
        }
        new_lines = []
        quantity = 0
        for requested in payload.lines:
            product = (await db.execute(
                select(Product).where(
                    Product.id == requested.product_id,
                    Product.is_active.is_(True),
                    Product.is_add_on.is_(True),
                )
            )).scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail=f"Active product {requested.product_id} not found.")
            variant = None
            adjustment = Decimal("0.00")
            if requested.product_variant_id:
                variant = (await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == requested.product_variant_id,
                        ProductVariant.product_id == product.id,
                        ProductVariant.is_active.is_(True),
                    )
                )).scalar_one_or_none()
                if not variant:
                    raise HTTPException(status_code=404, detail=f"Active variant {requested.product_variant_id} not found for {product.name}.")
                adjustment = Decimal(str(variant.price_adjustment))
            price = (Decimal(str(product.sales_price)) + adjustment).quantize(Decimal("0.01"))
            tax_rule_id = existing_tax_rules.get((product.id, variant.id if variant else None))
            new_lines.append((product, variant, requested.quantity, price, tax_rule_id))
            quantity += requested.quantity
        purchased_quantity = sum(line.quantity for line in base_lines) + quantity
        if plan and purchased_quantity < plan.min_quantity:
            raise HTTPException(status_code=409, detail=f"This plan requires a minimum quantity of {plan.min_quantity}.")
        old_lines = [
            {"product_id": str(line.product_id), "variant_id": str(line.product_variant_id), "quantity": line.quantity}
            for line in addon_lines
        ]
        effective_date = max(subscription.next_billing_date or today, today)
        for line in addon_lines:
            await db.delete(line)
        await db.flush()
        for product, variant, line_quantity, price, tax_rule_id in new_lines:
            db.add(SubscriptionLine(
                subscription_id=subscription.id,
                product_id=product.id,
                product_variant_id=variant.id if variant else None,
                quantity=line_quantity,
                unit_price=price,
                tax_rule_id=tax_rule_id,
            ))
        changes["lines"] = {
            "from": old_lines,
            "to": [
                {"product_id": str(product.id), "variant_id": str(variant.id) if variant else None, "quantity": line_quantity}
                for product, variant, line_quantity, _, _ in new_lines
            ],
            "effective_date": effective_date.isoformat(),
        }

    changes.update({
        "status": {"from": old_status.value, "to": subscription.status.value},
        "effective_date": effective_date.isoformat(),
    })
    await record_audit_event(
        db,
        entity_type="subscription",
        entity_id=subscription.id,
        action=f"CUSTOMER_{action.upper()}",
        actor_user_id=customer_user.id,
        changes=changes,
    )
    subject, message_body = portal_subscription_update_email(
        customer_name=customer_user.full_name,
        action=action,
        subscription_number=subscription.subscription_number,
        effective_date=effective_date,
        status=subscription.status.value,
    )
    await _notify_customer(db, user=customer_user, account=account, subject=subject, body=message_body)
    await db.commit()
    return PortalSubscriptionActionResponse(
        message=f"Your {action.replace('_', ' ')} change was applied.",
        status=subscription.status.value,
        effective_date=effective_date,
        cancel_at_period_end=subscription.cancel_at_period_end,
    )


@router.get("/payments", response_model=PortalPaymentPage)
async def list_customer_payments(
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Paginated payment history limited to invoices belonging to this customer's account."""
    membership = await _customer_membership(customer_user, db)
    query = (
        select(Payment, Invoice)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.customer_account_id == membership.customer_account_id)
        .options(selectinload(Payment.reversals))
        .order_by(Payment.payment_date.desc(), Payment.created_at.desc())
    )
    count = await db.scalar(
        select(func.count(Payment.id))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Invoice.customer_account_id == membership.customer_account_id)
    ) or 0
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()
    return PortalPaymentPage(
        items=[
            PortalPaymentResponse(
                id=payment.id,
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                amount=payment.amount,
                currency=invoice.currency,
                payment_method=payment.payment_method,
                payment_date=payment.payment_date,
                reference_note=payment.reference_note,
                is_reversed=payment.is_reversed,
                refunded_amount=sum(
                    (Decimal(str(reversal.reversal_amount)) for reversal in payment.reversals),
                    Decimal("0.00"),
                ),
                net_amount=Decimal(str(payment.amount)) - sum(
                    (Decimal(str(reversal.reversal_amount)) for reversal in payment.reversals),
                    Decimal("0.00"),
                ),
            )
            for payment, invoice in rows
        ],
        total=count,
        page=page,
        page_size=page_size,
        total_pages=max(1, (count + page_size - 1) // page_size),
    )


def _safe_pdf_text(value) -> str:
    return str(value or "").encode("latin-1", errors="replace").decode("latin-1")


def _invoice_pdf(invoice: Invoice) -> bytes:
    """Render a small, self-contained invoice PDF from immutable invoice snapshots."""
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=letter)
    _, height = letter
    y = height - 54

    def write(text: str, *, bold: bool = False, size: int = 10, gap: int = 16):
        nonlocal y
        if y < 54:
            pdf.showPage()
            y = height - 54
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        pdf.drawString(48, y, _safe_pdf_text(text)[:110])
        y -= gap

    write("BRIGHTLOOP SOFTWARE", bold=True, size=18, gap=28)
    write("INVOICE", bold=True, size=13)
    write(f"Invoice: {invoice.invoice_number}", bold=True)
    write(f"Customer: {invoice.customer_snapshot.get('company_name', 'Customer')}")
    write(f"Issue date: {invoice.issue_date}    Due date: {invoice.due_date}")
    write(f"Billing period: {invoice.billing_period_start} to {invoice.billing_period_end}")
    write(f"Currency: {invoice.currency}")
    y -= 8
    write("Description / Product", bold=True)
    write("Qty     Unit price       Subtotal        Discount        Tax           Total", bold=True)
    for line in invoice.lines:
        label = line.product_name_snapshot
        if line.variant_name_snapshot:
            label += f" ({line.variant_name_snapshot})"
        write(label, bold=True, gap=13)
        write(
            f"{line.quantity}       {line.unit_price_snapshot}       {line.subtotal}       "
            f"{line.discount_amount}       {line.tax_amount}       {line.line_total}",
            size=9,
        )
    y -= 8
    write(f"Subtotal: {invoice.subtotal} {invoice.currency}", bold=True)
    write(f"Discount: {invoice.discount_amount} {invoice.currency}")
    write(f"Tax: {invoice.tax_amount} {invoice.currency}")
    write(f"Total: {invoice.total_amount} {invoice.currency}", bold=True, size=13)
    write(f"Paid: {invoice.paid_amount} {invoice.currency}")
    write(f"Outstanding: {invoice.outstanding_balance} {invoice.currency}", bold=True)
    pdf.save()
    return output.getvalue()


@router.get("/invoices/{invoice_id}/pdf")
async def download_customer_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
):
    membership = await _customer_membership(customer_user, db)
    invoice = (await db.execute(
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.customer_account_id == membership.customer_account_id,
            Invoice.status != InvoiceStatus.DRAFT,
        )
        .options(selectinload(Invoice.lines))
    )).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    pdf_bytes = _invoice_pdf(invoice)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )
