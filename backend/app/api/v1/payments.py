import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod
from app.schemas.invoice import RecordPaymentRequest, PaymentResponse
from app.api.v1.deps import require_staff_or_admin, get_current_user
from app.models.user import User
from app.services.audit import record_audit_event

router = APIRouter()


@router.get("", response_model=List[PaymentResponse], tags=["Payments"])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """List all recorded payments."""
    query = select(Payment).order_by(Payment.created_at.desc())
    result = await db.execute(query)
    payments = result.scalars().all()
    return [PaymentResponse.model_validate(p) for p in payments]


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED, tags=["Payments"])
async def record_payment(
    payload: RecordPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Record an append-only payment against an invoice.
    Atomically updates invoice paid_amount and sets status to PAID if fully settled.
    """
    query = select(Invoice).where(Invoice.id == payload.invoice_id)
    invoice = (await db.execute(query)).scalar_one_or_none()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT):
        raise HTTPException(status_code=400, detail="Cannot record payment on draft or cancelled invoice.")

    # 1. Create append-only payment record
    new_payment = Payment(
        invoice_id=invoice.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_date=payload.payment_date,
        reference_note=payload.reference_note,
        recorded_by_user_id=current_user.id,
    )
    db.add(new_payment)
    await db.flush()

    # Record Audit Event
    await record_audit_event(
        db,
        entity_type="payment",
        entity_id=new_payment.id,
        action="CREATE_PAYMENT",
        actor_user_id=current_user.id,
        changes={
            "invoice_id": str(invoice.id),
            "amount": str(payload.amount),
            "payment_method": str(payload.payment_method),
        },
    )

    # 2. Update invoice paid_amount
    invoice.paid_amount = Decimal(str(invoice.paid_amount)) + payload.amount
    if invoice.paid_amount >= invoice.total_amount:
        invoice.status = InvoiceStatus.PAID

    await db.commit()
    await db.refresh(new_payment)
    return PaymentResponse.model_validate(new_payment)

