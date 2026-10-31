import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.clock import organization_today
from app.models.invoice import Invoice, InvoiceStatus
from app.models.customer import CustomerAccount
from app.models.payment import Payment, PaymentMethod, PaymentReversal
from app.models.outbox import OutboxMessage
from app.models.user import User
from app.models.audit import AuditEvent
from app.schemas.payment import (
    RecordPaymentRequest,
    PaymentResponse,
    PaymentDetailResponse,
    PaymentReversalRequest,
    PaymentReversalResponse,
    CollectionQueueSummary,
    CollectionItemResponse,
    AgingBucketSummary,
    SendOverdueReminderRequest,
    PaymentWebhookPayload,
)
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event
from app.services.email_templates import payment_receipt_email, payment_refund_email, overdue_reminder_email, overdue_reminder_window
from app.services.outbox import create_outbox_message
from app.services.payment_adapters import get_payment_adapter

router = APIRouter()


def _payment_options():
    return (
        selectinload(Payment.invoice).selectinload(Invoice.customer_account),
        selectinload(Payment.reversals),
    )


def _build_payment_detail(payment: Payment) -> PaymentDetailResponse:
    invoice = payment.invoice
    customer_name = None
    invoice_number = None
    currency = "USD"
    if invoice:
        invoice_number = invoice.invoice_number
        currency = invoice.currency
        if invoice.customer_account:
            customer_name = invoice.customer_account.company_name
        elif invoice.customer_snapshot:
            customer_name = invoice.customer_snapshot.get("company_name")

    reversal_responses = [
        PaymentReversalResponse(
            id=reversal.id,
            payment_id=reversal.payment_id,
            reversal_amount=reversal.reversal_amount,
            reason=reversal.reason,
            reversed_by_user_id=reversal.reversed_by_user_id,
            reversed_at=reversal.reversed_at,
        )
        for reversal in payment.reversals
    ]

    return PaymentDetailResponse(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        payment_method=payment.payment_method,
        payment_date=payment.payment_date,
        reference_note=payment.reference_note,
        is_reversed=payment.is_reversed,
        created_at=payment.created_at,
        reversal=reversal_responses[-1] if reversal_responses else None,
        reversals=reversal_responses,
        customer_name=customer_name,
        invoice_number=invoice_number,
        currency=currency,
    )


@router.get("", response_model=Union[PaginatedResponse[PaymentDetailResponse], List[PaymentDetailResponse]], tags=["Payments"])
async def list_payments(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(15, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by invoice number, reference note, or customer"),
    payment_method: Optional[str] = Query(None, description="Filter by payment method"),
    is_reversed: Optional[bool] = Query(None, description="Filter by reversal status"),
    invoice_id: Optional[uuid.UUID] = Query(None, description="Filter by specific invoice"),
    envelope: bool = Query(False, description="Return enveloped pagination object"),
):
    """
    List all recorded payments with search, filters (method, reversal status), and pagination.
    """
    query = (
        select(Payment)
        .outerjoin(Invoice, Payment.invoice_id == Invoice.id)
        .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
        .options(*_payment_options())
    )
    count_query = (
        select(func.count(distinct(Payment.id)))
        .select_from(Payment)
        .outerjoin(Invoice, Payment.invoice_id == Invoice.id)
        .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
    )

    filters = []
    if invoice_id:
        filters.append(Payment.invoice_id == invoice_id)

    if is_reversed is not None:
        filters.append(Payment.is_reversed == is_reversed)

    if payment_method:
        try:
            method_enum = PaymentMethod(payment_method.lower().strip())
            filters.append(Payment.payment_method == method_enum)
        except ValueError:
            pass

    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Payment.reference_note.ilike(term),
                Invoice.invoice_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
            )
        )

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_count = (await db.execute(count_query)).scalar_one()

    query = query.order_by(Payment.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    payments = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    items = [_build_payment_detail(p) for p in payments]

    if envelope:
        return PaginatedResponse[PaymentDetailResponse](
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return items


@router.get("/collection-queue", response_model=CollectionQueueSummary, tags=["Payments"])
async def get_collection_queue(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
    search: Optional[str] = Query(None, description="Search by customer name or invoice number"),
    aging_bucket: Optional[str] = Query(None, description="Filter by aging bucket: 1-30, 31-60, 61-90, 90_plus"),
    min_balance: Optional[Decimal] = Query(None, description="Filter for minimum balance due"),
    sort_by: Optional[str] = Query("days_overdue", description="Sort by: days_overdue, balance, due_date"),
    sort_order: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
):
    """
    Overdue Collection Queue:
    Retrieves all overdue invoices where balance > 0 and due_date < today.
    Groups items by aging buckets and sorts by overdue age and outstanding balance.
    """
    today = organization_today()

    query = (
        select(Invoice)
        .where(
            Invoice.status == InvoiceStatus.CONFIRMED,
            Invoice.due_date < today,
            (Invoice.total_amount - Invoice.paid_amount) > Decimal("0.00"),
        )
        .options(selectinload(Invoice.customer_account))
    )

    result = await db.execute(query)
    overdue_invoices = result.scalars().all()

    # Pre-fetch last reminder audit events for these invoices
    inv_ids = [inv.id for inv in overdue_invoices]
    last_reminder_map = {}
    if inv_ids:
        audit_query = (
            select(AuditEvent.entity_id, func.max(AuditEvent.timestamp))
            .where(
                AuditEvent.entity_type == "invoice",
                AuditEvent.entity_id.in_(inv_ids),
                AuditEvent.action == "SEND_COLLECTION_REMINDER",
            )
            .group_by(AuditEvent.entity_id)
        )
        audit_res = await db.execute(audit_query)
        for row in audit_res.all():
            last_reminder_map[row[0]] = row[1]

    items: List[CollectionItemResponse] = []
    bucket_counts = {
        "1-30": AgingBucketSummary(),
        "31-60": AgingBucketSummary(),
        "61-90": AgingBucketSummary(),
        "90_plus": AgingBucketSummary(),
    }
    total_balance = Decimal("0.00")

    for inv in overdue_invoices:
        balance = inv.total_amount - inv.paid_amount
        days = (today - inv.due_date).days
        if 1 <= days <= 30:
            b_key = "1-30"
            b_label = "1-30 days"
        elif 31 <= days <= 60:
            b_key = "31-60"
            b_label = "31-60 days"
        elif 61 <= days <= 90:
            b_key = "61-90"
            b_label = "61-90 days"
        else:
            b_key = "90_plus"
            b_label = "90+ days"

        cust_name = inv.customer_account.company_name if inv.customer_account else (inv.customer_snapshot or {}).get("company_name", "Customer")
        email = inv.customer_account.billing_email if inv.customer_account else (inv.customer_snapshot or {}).get("billing_email")

        # Filter by search if specified
        if search and search.strip():
            st = search.strip().lower()
            if st not in inv.invoice_number.lower() and st not in cust_name.lower():
                continue

        # Filter by min_balance if specified
        if min_balance is not None and balance < min_balance:
            continue

        # Filter by aging_bucket if specified
        if aging_bucket and aging_bucket.strip():
            ab = aging_bucket.strip()
            if ab == "90+" or ab == "90_plus":
                if b_key != "90_plus":
                    continue
            elif b_key != ab:
                continue

        total_balance += balance
        bucket_counts[b_key].count += 1
        bucket_counts[b_key].amount += balance

        items.append(
            CollectionItemResponse(
                invoice_id=inv.id,
                invoice_number=inv.invoice_number,
                customer_account_id=inv.customer_account_id,
                customer_name=cust_name,
                billing_email=email,
                total_amount=inv.total_amount,
                paid_amount=inv.paid_amount,
                balance_due=balance,
                currency=inv.currency,
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                days_overdue=days,
                aging_bucket=b_label,
                last_reminder_sent_at=last_reminder_map.get(inv.id),
            )
        )

    # Sort collection items
    is_desc = (sort_order or "desc").lower() == "desc"
    if sort_by == "balance":
        items.sort(key=lambda x: x.balance_due, reverse=is_desc)
    elif sort_by == "due_date":
        items.sort(key=lambda x: x.due_date, reverse=is_desc)
    else:  # default: days_overdue
        items.sort(key=lambda x: (x.days_overdue, x.balance_due), reverse=is_desc)

    return CollectionQueueSummary(
        total_overdue_balance=total_balance,
        total_overdue_invoices=len(overdue_invoices),
        aging_breakdown=bucket_counts,
        items=items,
    )


@router.post("/collection-queue/{invoice_id}/remind", tags=["Payments"])
async def send_collection_reminder(
    invoice_id: uuid.UUID,
    payload: Optional[SendOverdueReminderRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Dispatch an overdue payment reminder notification for an overdue invoice.
    Uses the durable outbox with idempotency to prevent repeated reminders on the same calendar day.
    """
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.customer_account))
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    balance = inv.total_amount - inv.paid_amount
    if balance <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Invoice has no outstanding balance.")

    recipient = (inv.customer_snapshot or {}).get("billing_email")
    if not recipient and inv.customer_account:
        recipient = inv.customer_account.billing_email

    if not recipient:
        raise HTTPException(status_code=400, detail="Customer billing email is missing.")

    today = organization_today()
    subject, default_body = overdue_reminder_email(
        invoice_number=inv.invoice_number,
        due_date=inv.due_date,
        balance=balance,
        currency=inv.currency,
    )

    body = default_body
    if payload and payload.custom_message and payload.custom_message.strip():
        body = f"{default_body}\n\nNote from Finance:\n{payload.custom_message.strip()}"

    days_overdue = (today - inv.due_date).days
    reminder_window = overdue_reminder_window(days_overdue)
    dedupe_key = f"overdue-reminder:{inv.id}:{reminder_window}"
    existing_reminder = (await db.execute(
        select(OutboxMessage).where(OutboxMessage.dedupe_key == dedupe_key)
    )).scalar_one_or_none()
    if existing_reminder:
        return {
            "status": existing_reminder.status,
            "message": f"A reminder for invoice {inv.invoice_number} is already {existing_reminder.status} in this overdue window.",
            "dedupe_key": dedupe_key,
        }
    await create_outbox_message(
        db,
        topic="email",
        dedupe_key=dedupe_key,
        payload={
            "type": "overdue_reminder",
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "to": recipient,
            "subject": subject,
            "body": body,
            "balance": str(balance),
            "due_date": inv.due_date.isoformat(),
        },
    )

    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=inv.id,
        action="SEND_COLLECTION_REMINDER",
        actor_user_id=current_user.id,
        changes={
            "invoice_number": inv.invoice_number,
            "balance_due": str(balance),
            "recipient": recipient,
            "dedupe_key": dedupe_key,
        },
    )

    await db.commit()
    return {
        "status": "queued",
        "message": f"Overdue reminder for invoice {inv.invoice_number} dispatched to {recipient}.",
        "dedupe_key": dedupe_key,
    }


@router.get("/{payment_id}", response_model=PaymentDetailResponse, tags=["Payments"])
async def get_payment(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """Get single payment details including invoice and reversal info."""
    query = (
        select(Payment)
        .where(Payment.id == payment_id)
        .options(*_payment_options())
    )
    payment = (await db.execute(query)).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return _build_payment_detail(payment)


@router.post("", response_model=PaymentDetailResponse, status_code=status.HTTP_201_CREATED, tags=["Payments"])
async def record_payment(
    payload: RecordPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Record an append-only payment against an invoice.
    Supports partial payments, validates against remaining balance,
    and transitions confirmed invoice to PAID when fully settled.
    """
    query = (
        select(Invoice)
        .where(Invoice.id == payload.invoice_id)
        .options(selectinload(Invoice.customer_account))
        .with_for_update()
    )
    invoice = (await db.execute(query)).scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot record payment against an invoice in '{invoice.status.value}' status. Invoice must be confirmed first.",
        )

    remaining_balance = invoice.total_amount - invoice.paid_amount
    if remaining_balance <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Invoice is already fully paid.")

    if payload.amount <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero.")

    if payload.amount > remaining_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({payload.amount}) cannot exceed remaining balance ({remaining_balance} {invoice.currency}).",
        )

    # Invoke payment provider adapter
    adapter = get_payment_adapter("manual")
    adapter_result = await adapter.process_payment(
        invoice_id=invoice.id,
        amount=payload.amount,
        currency=invoice.currency,
        payment_method=payload.payment_method.value,
        reference_note=payload.reference_note,
    )

    if not adapter_result.success:
        raise HTTPException(status_code=400, detail=f"Payment processing failed: {adapter_result.message}")

    # 1. Create append-only payment record
    new_payment = Payment(
        invoice_id=invoice.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_date=payload.payment_date,
        reference_note=payload.reference_note or adapter_result.external_reference,
        recorded_by_user_id=current_user.id,
    )
    db.add(new_payment)
    await db.flush()

    # 2. Update invoice paid_amount atomically
    invoice.paid_amount = invoice.paid_amount + payload.amount
    if invoice.paid_amount >= invoice.total_amount:
        invoice.status = InvoiceStatus.PAID

    # Record Audit Event
    await record_audit_event(
        db,
        entity_type="payment",
        entity_id=new_payment.id,
        action="CREATE_PAYMENT",
        actor_user_id=current_user.id,
        changes={
            "invoice_id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "amount": str(payload.amount),
            "payment_method": str(payload.payment_method.value),
            "new_invoice_status": invoice.status.value,
            "new_paid_amount": str(invoice.paid_amount),
            "remaining_balance": str(invoice.total_amount - invoice.paid_amount),
        },
    )

    # Queue payment receipt email
    recipient = (invoice.customer_snapshot or {}).get("billing_email")
    if not recipient and invoice.customer_account:
        recipient = invoice.customer_account.billing_email

    if recipient:
        method = payload.payment_method.value
        balance = max(Decimal("0.00"), invoice.total_amount - invoice.paid_amount)
        subject, body = payment_receipt_email(
            company_name=(invoice.customer_snapshot or {}).get("company_name") or (invoice.customer_account.company_name if invoice.customer_account else "Customer"),
            invoice_number=invoice.invoice_number,
            amount=payload.amount,
            currency=invoice.currency,
            payment_method=method,
            payment_date=payload.payment_date,
            balance=balance,
        )
        await create_outbox_message(
            db,
            topic="email",
            dedupe_key=f"payment-receipt:{new_payment.id}",
            payload={
                "type": "payment_receipt",
                "payment_id": str(new_payment.id),
                "invoice_id": str(invoice.id),
                "to": recipient,
                "subject": subject,
                "body": body,
                "amount": str(payload.amount),
                "balance": str(balance),
            },
        )

    await db.commit()

    # Re-fetch with relationships for complete response
    query = (
        select(Payment)
        .where(Payment.id == new_payment.id)
        .options(*_payment_options())
    )
    saved = (await db.execute(query)).scalar_one()
    return _build_payment_detail(saved)


@router.post("/{payment_id}/reverse", response_model=PaymentDetailResponse, tags=["Payments"])
async def reverse_payment(
    payment_id: uuid.UUID,
    payload: PaymentReversalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Reverse or refund a previously recorded payment.
    Creates an immutable PaymentReversal record, marks payment as reversed,
    adjusts invoice paid_amount, and un-settles invoice back to CONFIRMED if previously PAID.
    """
    query = (
        select(Payment)
        .where(Payment.id == payment_id)
        .options(*_payment_options())
        .with_for_update()
    )
    payment = (await db.execute(query)).scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found.")

    already_reversed = sum(
        (Decimal(str(item.reversal_amount)) for item in payment.reversals),
        Decimal("0.00"),
    )
    remaining_reversible = Decimal(str(payment.amount)) - already_reversed
    if remaining_reversible <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="This payment has already been fully reversed/refunded.")

    reversal_amount = payload.amount if payload.amount is not None else remaining_reversible
    if reversal_amount <= Decimal("0.00"):
        raise HTTPException(status_code=400, detail="Reversal amount must be greater than zero.")

    if reversal_amount > remaining_reversible:
        raise HTTPException(
            status_code=400,
            detail=f"Reversal amount ({reversal_amount}) cannot exceed the remaining refundable amount ({remaining_reversible}).",
        )

    # Adapter execution
    adapter = get_payment_adapter("manual")
    adapter_result = await adapter.process_refund(
        payment_id=payment.id,
        amount=reversal_amount,
        reason=payload.reason,
    )
    if not adapter_result.success:
        raise HTTPException(status_code=400, detail=f"Reversal processing failed: {adapter_result.message}")

    # Create immutable PaymentReversal record
    reversal = PaymentReversal(
        payment_id=payment.id,
        reversal_amount=reversal_amount,
        reason=payload.reason.strip(),
        reversed_by_user_id=current_user.id,
    )
    db.add(reversal)
    await db.flush()
    payment.is_reversed = already_reversed + reversal_amount >= Decimal(str(payment.amount))

    # Adjust invoice paid_amount and status
    invoice = (await db.execute(
        select(Invoice)
        .where(Invoice.id == payment.invoice_id)
        .options(selectinload(Invoice.customer_account))
        .with_for_update()
    )).scalar_one_or_none()
    if invoice:
        old_paid = invoice.paid_amount
        invoice.paid_amount = max(Decimal("0.00"), invoice.paid_amount - reversal_amount)

        if invoice.status == InvoiceStatus.PAID and invoice.paid_amount < invoice.total_amount:
            invoice.status = InvoiceStatus.CONFIRMED

        # Record audit event on invoice
        await record_audit_event(
            db,
            entity_type="payment",
            entity_id=payment.id,
            action="REVERSE_PAYMENT",
            actor_user_id=current_user.id,
            changes={
                "payment_id": str(payment.id),
                "invoice_id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "reversal_amount": str(reversal_amount),
                "remaining_refundable_amount": str(max(Decimal("0.00"), remaining_reversible - reversal_amount)),
                "reason": payload.reason.strip(),
                "old_paid_amount": str(old_paid),
                "new_paid_amount": str(invoice.paid_amount),
                "new_invoice_status": invoice.status.value,
            },
        )

        # Dispatch refund email notice
        recipient = (invoice.customer_snapshot or {}).get("billing_email")
        if not recipient and invoice.customer_account:
            recipient = invoice.customer_account.billing_email

        if recipient:
            cust_name = (invoice.customer_snapshot or {}).get("company_name") or (invoice.customer_account.company_name if invoice.customer_account else "Customer")
            subject, body = payment_refund_email(
                company_name=cust_name,
                invoice_number=invoice.invoice_number,
                amount=reversal_amount,
                currency=invoice.currency,
                reason=payload.reason.strip(),
                balance=invoice.total_amount - invoice.paid_amount,
            )
            await create_outbox_message(
                db,
                topic="email",
                dedupe_key=f"payment-refund:{reversal.id}",
                payload={
                    "type": "payment_refund",
                    "payment_id": str(payment.id),
                    "invoice_id": str(invoice.id),
                    "to": recipient,
                    "subject": subject,
                    "body": body,
                    "amount": str(reversal_amount),
                },
            )

    await db.commit()

    # Re-fetch for response
    query = (
        select(Payment)
        .where(Payment.id == payment.id)
        .options(*_payment_options())
        .execution_options(populate_existing=True)
    )
    refreshed = (await db.execute(query)).scalar_one()
    return _build_payment_detail(refreshed)


@router.post("/webhooks/{provider}", tags=["Payments"])
async def receive_provider_webhook(
    provider: str,
    payload: PaymentWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Extensible webhook endpoint for payment provider integrations.
    Processes webhook events through registered payment provider adapters.
    """
    adapter = get_payment_adapter(provider)
    result = await adapter.handle_webhook(payload.model_dump())
    return {
        "status": "acknowledged",
        "provider": provider,
        "result": result.model_dump(),
    }
