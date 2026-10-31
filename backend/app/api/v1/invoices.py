import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.customer import CustomerAccount
from app.schemas.invoice import InvoiceResponse, InvoiceLineResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get("", response_model=List[InvoiceResponse], tags=["Invoices"])
async def list_invoices(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """List all issued and draft invoices for admin/staff."""
    query = (
        select(Invoice)
        .options(
            selectinload(Invoice.customer_account),
            selectinload(Invoice.lines),
        )
        .order_by(Invoice.issue_date.desc())
    )
    result = await db.execute(query)
    invoices = result.scalars().all()

    response = []
    for inv in invoices:
        line_resps = [
            InvoiceLineResponse(
                id=l.id,
                description=l.description,
                product_name_snapshot=l.product_name_snapshot,
                variant_name_snapshot=l.variant_name_snapshot,
                quantity=l.quantity,
                unit_price_snapshot=l.unit_price_snapshot,
                subtotal=l.subtotal,
                tax_amount=l.tax_amount,
                discount_amount=l.discount_amount,
                line_total=l.line_total,
            )
            for l in inv.lines
        ]

        response.append(
            InvoiceResponse(
                id=inv.id,
                invoice_number=inv.invoice_number,
                subscription_id=inv.subscription_id,
                customer_account_id=inv.customer_account_id,
                customer_name=inv.customer_account.company_name if inv.customer_account else "Customer",
                currency=inv.currency,
                status=inv.status,
                billing_period_start=inv.billing_period_start,
                billing_period_end=inv.billing_period_end,
                subtotal=inv.subtotal,
                tax_amount=inv.tax_amount,
                discount_amount=inv.discount_amount,
                total_amount=inv.total_amount,
                paid_amount=inv.paid_amount,
                outstanding_balance=inv.outstanding_balance,
                is_overdue=inv.is_overdue,
                issue_date=inv.issue_date,
                due_date=inv.due_date,
                send_status=inv.send_status,
                lines=line_resps,
            )
        )
    return response


@router.post("/{invoice_id}/confirm", tags=["Invoices"])
async def confirm_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Confirm a draft invoice."""
    query = select(Invoice).where(Invoice.id == invoice_id)
    inv = (await db.execute(query)).scalar_one_or_none()

    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be confirmed.")

    inv.status = InvoiceStatus.CONFIRMED
    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=inv.id,
        action="CONFIRM",
        actor_user_id=_user.id,
        changes={"invoice_number": inv.invoice_number, "status": inv.status.value},
    )
    await db.commit()
    return {"message": f"Invoice {inv.invoice_number} confirmed.", "status": inv.status}

