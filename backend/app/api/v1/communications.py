"""Quote/invoice email actions and delivery-failure operations for staff."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_staff_or_admin
from app.core.clock import organization_today
from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.outbox import OutboxMessage, OutboxMessageStatus
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.portal import OutboxMessageResponse
from app.services.audit import record_audit_event
from app.services.billing import _load_pricing_rules, calculate_subscription_charge
from app.services.email_templates import quotation_email
from app.services.outbox import create_outbox_message

router = APIRouter(tags=["Communications"])


def _outbox_response(message: OutboxMessage) -> OutboxMessageResponse:
    payload = message.payload or {}
    message_type = payload.get("type")
    subject = payload.get("subject")
    if message_type == "invoice_issued" and not subject:
        subject = f"Invoice {payload.get('invoice_number', '')} from Brightloop Software"
    return OutboxMessageResponse(
        id=message.id,
        topic=message.topic,
        message_type=message_type,
        recipient=payload.get("to") or payload.get("recipient_email"),
        subject=subject,
        status=message.status,
        retry_count=message.retry_count,
        max_retries=message.max_retries,
        last_error=message.last_error,
        scheduled_at=message.scheduled_at,
        sent_at=message.sent_at,
        created_at=message.created_at,
    )


@router.post("/subscriptions/{subscription_id}/send-quote")
async def send_quotation_email(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    subscription = (await db.execute(
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if subscription.status != SubscriptionStatus.QUOTATION:
        raise HTTPException(status_code=409, detail="Only issued quotations can be emailed.")
    if subscription.quote_valid_until and subscription.quote_valid_until < organization_today():
        raise HTTPException(status_code=409, detail="This quotation has expired.")
    account = subscription.customer_account
    if not account or not account.billing_email:
        raise HTTPException(status_code=409, detail="The customer has no billing email address.")

    tax_map, default_tax_rule, discounts, redemptions = await _load_pricing_rules(db)
    charge = calculate_subscription_charge(
        subscription,
        tax_map=tax_map,
        default_tax_rule=default_tax_rule,
        discount_rules=discounts,
        redemption_counts=redemptions,
        as_of=subscription.start_date,
    )
    line_text = "\n".join(
        f"- {line.product_name}{f' ({line.variant_name})' if line.variant_name else ''} × {line.quantity}: "
        f"{line.line_total} {account.currency}"
        for line in charge.lines
    )
    subject, body = quotation_email(
        company_name=account.company_name,
        quote_number=subscription.subscription_number,
        plan_name=subscription.plan.name if subscription.plan else "Subscription plan",
        start_date=subscription.start_date,
        valid_until=subscription.quote_valid_until,
        lines=line_text.splitlines(),
        subtotal=charge.subtotal,
        discount=charge.discount,
        tax=charge.tax,
        total=charge.total,
        currency=account.currency,
    )
    message = await create_outbox_message(
        db,
        topic="email",
        payload={"type": "quote_issued", "to": account.billing_email, "subject": subject, "body": body},
    )
    await record_audit_event(
        db,
        entity_type="subscription",
        entity_id=subscription.id,
        action="SEND_QUOTATION_EMAIL",
        actor_user_id=current_user.id,
        changes={"outbox_message_id": str(message.id), "recipient": account.billing_email},
    )
    await db.commit()
    return {"message": "Quotation email queued.", "outbox_message_id": str(message.id)}


@router.post("/invoices/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    invoice = (await db.execute(select(Invoice).where(Invoice.id == invoice_id))).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.status in (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Only confirmed or paid invoices can be emailed.")
    recipient = (invoice.customer_snapshot or {}).get("billing_email")
    if not recipient:
        raise HTTPException(status_code=409, detail="The invoice has no billing email address.")
    message = await create_outbox_message(
        db,
        topic="email",
        payload={
            "type": "invoice_issued",
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "recipient_email": recipient,
            "total_amount": str(invoice.total_amount),
            "due_date": invoice.due_date.isoformat(),
            "currency": invoice.currency,
        },
    )
    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action="SEND_INVOICE_EMAIL",
        actor_user_id=current_user.id,
        changes={"outbox_message_id": str(message.id), "recipient": recipient},
    )
    await db.commit()
    return {"message": "Invoice email queued.", "outbox_message_id": str(message.id)}


@router.get("/outbox", response_model=PaginatedResponse[OutboxMessageResponse])
async def list_outbox_messages(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    query = select(OutboxMessage).where(OutboxMessage.topic == "email")
    count_query = select(func.count(OutboxMessage.id)).where(OutboxMessage.topic == "email")
    if status_filter:
        state = status_filter.strip().upper()
        query = query.where(OutboxMessage.status == state)
        count_query = count_query.where(OutboxMessage.status == state)
    total = await db.scalar(count_query) or 0
    messages = (await db.execute(
        query.order_by(OutboxMessage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return PaginatedResponse[OutboxMessageResponse](
        items=[_outbox_response(message) for message in messages],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.post("/outbox/{message_id}/retry", response_model=OutboxMessageResponse)
async def retry_outbox_message(
    message_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    message = (await db.execute(
        select(OutboxMessage).where(OutboxMessage.id == message_id).with_for_update()
    )).scalar_one_or_none()
    if not message or message.topic != "email":
        raise HTTPException(status_code=404, detail="Email delivery record not found.")
    if message.status != OutboxMessageStatus.FAILED.value:
        raise HTTPException(status_code=409, detail="Only failed email messages can be retried.")
    message.status = OutboxMessageStatus.PENDING.value
    message.retry_count = 0
    message.last_error = None
    message.scheduled_at = message.created_at
    await record_audit_event(
        db,
        entity_type="outbox_message",
        entity_id=message.id,
        action="RETRY_EMAIL_DELIVERY",
        actor_user_id=current_user.id,
        changes={"topic": message.topic},
    )
    await db.commit()
    await db.refresh(message)
    return _outbox_response(message)
