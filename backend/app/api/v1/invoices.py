import uuid
from typing import List, Optional, Union
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.clock import organization_today
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, SendStatus
from app.models.customer import CustomerAccount
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import BillingCadence
from app.models.payment import Payment
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.invoice import (
    InvoiceResponse,
    InvoiceLineResponse,
    InvoiceDetailResponse,
    InvoiceAuditItem,
    PaymentResponse,
    GenerateDraftInvoiceRequest,
    CancelInvoiceRequest,
)
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event
from app.services.outbox import create_outbox_message
from app.services.billing import generate_invoice_for_subscription, compute_next_billing_date

router = APIRouter()


def _invoice_options():
    return (
        selectinload(Invoice.customer_account),
        selectinload(Invoice.lines),
        selectinload(Invoice.payments),
    )


def _line_to_response(line: InvoiceLine) -> InvoiceLineResponse:
    return InvoiceLineResponse(
        id=line.id,
        description=line.description,
        product_name_snapshot=line.product_name_snapshot,
        variant_name_snapshot=line.variant_name_snapshot,
        quantity=line.quantity,
        unit_price_snapshot=line.unit_price_snapshot,
        subtotal=line.subtotal,
        tax_rule_name_snapshot=line.tax_rule_name_snapshot,
        tax_rate_snapshot=line.tax_rate_snapshot,
        tax_amount=line.tax_amount,
        discount_rule_name_snapshot=line.discount_rule_name_snapshot,
        discount_amount=line.discount_amount,
        line_total=line.line_total,
    )


def _invoice_to_response(inv: Invoice) -> InvoiceResponse:
    return InvoiceResponse(
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
        lines=[_line_to_response(l) for l in inv.lines],
    )


@router.get(
    "",
    response_model=Union[PaginatedResponse[InvoiceResponse], List[InvoiceResponse]],
    tags=["Invoices"],
)
async def list_invoices(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for invoice # or customer name"),
    status: Optional[str] = Query(None, description="Filter by status: draft, confirmed, paid, cancelled, or 'overdue'"),
    sort_by: Optional[str] = Query("issue_date", description="Sort field: issue_date, due_date, total_amount, outstanding_balance, invoice_number"),
    sort_order: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """
    List all issued and draft invoices for admin/staff with server-side search, filtering, sorting, and pagination.
    Emits pagination headers (X-Total-Count, X-Page, X-Page-Size, X-Total-Pages).
    """
    query = (
        select(Invoice)
        .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
        .options(*_invoice_options())
    )
    count_query = (
        select(func.count(distinct(Invoice.id)))
        .select_from(Invoice)
        .outerjoin(CustomerAccount, Invoice.customer_account_id == CustomerAccount.id)
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Invoice.invoice_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
            )
        )

    if status and status.strip():
        s = status.strip().lower()
        if s == "overdue":
            filters.append(Invoice.is_overdue == True)  # noqa: E712
        else:
            if s == "canceled":
                s = "cancelled"
            try:
                status_enum = InvoiceStatus(s)
                filters.append(Invoice.status == status_enum)
            except ValueError:
                pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_count = (await db.execute(count_query)).scalar_one()

    sort_col = Invoice.issue_date
    if sort_by == "due_date":
        sort_col = Invoice.due_date
    elif sort_by == "total_amount":
        sort_col = Invoice.total_amount
    elif sort_by == "outstanding_balance":
        sort_col = Invoice.outstanding_balance
    elif sort_by == "invoice_number":
        sort_col = Invoice.invoice_number

    if sort_order and sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(sort_col.desc().nulls_last())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    invoices = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    items = [_invoice_to_response(inv) for inv in invoices]

    if envelope:
        return PaginatedResponse[InvoiceResponse](
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return items


@router.post(
    "/generate",
    response_model=InvoiceDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Invoices"],
)
async def generate_draft_invoice(
    payload: GenerateDraftInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Generate an invoice draft (or confirmed invoice) directly from an active subscription.
    Enforces idempotency, calculates taxes and discounts, freezes customer & line snapshots.
    """
    invoice = await generate_invoice_for_subscription(
        db,
        subscription_id=payload.subscription_id,
        actor_user_id=current_user.id,
        as_of=organization_today(),
        as_draft=payload.as_draft,
        period_start=payload.billing_period_start,
        period_end=payload.billing_period_end,
    )

    return await _build_invoice_detail_response(db, invoice.id)


@router.get(
    "/{invoice_id}",
    response_model=InvoiceDetailResponse,
    tags=["Invoices"],
)
async def get_invoice_detail(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """Get full details of an invoice, including immutable snapshots, payment history, and audit log."""
    return await _build_invoice_detail_response(db, invoice_id)


@router.post("/{invoice_id}/confirm", tags=["Invoices"])
async def confirm_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Confirm a draft invoice, making it an official financial demand."""
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(*_invoice_options())
    )
    inv = (await db.execute(query)).scalar_one_or_none()

    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft invoices can be confirmed.")

    inv.status = InvoiceStatus.CONFIRMED

    # Advance subscription next_billing_date if needed
    sub = (await db.execute(
        select(Subscription).where(Subscription.id == inv.subscription_id).options(selectinload(Subscription.plan))
    )).scalar_one_or_none()
    if sub and sub.status == SubscriptionStatus.ACTIVE:
        cadence = sub.plan.cadence if sub.plan else BillingCadence.MONTHLY
        sub.next_billing_date = compute_next_billing_date(
            inv.billing_period_start, cadence, sub.billing_anchor_day
        )

    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=inv.id,
        action="CONFIRM",
        actor_user_id=current_user.id,
        changes={"invoice_number": inv.invoice_number, "status": inv.status.value},
    )
    await db.commit()
    return {"message": f"Invoice {inv.invoice_number} confirmed.", "status": inv.status}


@router.post(
    "/{invoice_id}/cancel",
    response_model=InvoiceDetailResponse,
    tags=["Invoices"],
)
async def cancel_invoice(
    invoice_id: uuid.UUID,
    payload: CancelInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Cancel an invoice with a required audit reason.
    Paid invoices cannot be cancelled directly (must issue reversal/refund).
    """
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(*_invoice_options())
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if inv.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Invoice is already cancelled.")

    if inv.status == InvoiceStatus.PAID or inv.paid_amount > Decimal("0.00"):
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel an invoice with recorded payments. Reverse or refund payments first.",
        )

    old_status = inv.status.value
    inv.status = InvoiceStatus.CANCELLED
    inv.cancellation_reason = payload.reason.strip()

    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=inv.id,
        action="CANCEL",
        actor_user_id=current_user.id,
        changes={
            "invoice_number": inv.invoice_number,
            "old_status": old_status,
            "new_status": inv.status.value,
            "cancellation_reason": inv.cancellation_reason,
        },
    )
    await db.commit()
    return await _build_invoice_detail_response(db, inv.id)


@router.post(
    "/{invoice_id}/send",
    response_model=InvoiceDetailResponse,
    tags=["Invoices"],
)
async def send_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Send invoice notification email to customer via outbox and mark as sent."""
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(*_invoice_options())
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    if inv.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot send a cancelled invoice.")

    recipient_email = inv.customer_snapshot.get("billing_email")
    if not recipient_email and inv.customer_account:
        recipient_email = inv.customer_account.billing_email

    if not recipient_email:
        raise HTTPException(status_code=400, detail="Customer billing email is missing.")

    await create_outbox_message(
        db,
        topic="email",
        payload={
            "type": "invoice_issued",
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "to": recipient_email,
            "recipient_email": recipient_email,
            "subject": f"Invoice {inv.invoice_number} from Brightloop Software",
            "body": (
                f"Hello,\n\n"
                f"Your invoice {inv.invoice_number} for billing period "
                f"{inv.billing_period_start} through {inv.billing_period_end} is ready.\n\n"
                f"Amount Due: {inv.total_amount} {inv.currency}\n"
                f"Due Date: {inv.due_date}\n\n"
                f"Please review your invoice in the customer portal.\n\n"
                f"Thank you,\nBrightloop Software"
            ),
            "total_amount": str(inv.total_amount),
            "due_date": inv.due_date.isoformat(),
        },
    )

    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=inv.id,
        action="SEND",
        actor_user_id=current_user.id,
        changes={
            "invoice_number": inv.invoice_number,
            "recipient_email": recipient_email,
            "send_status": inv.send_status.value,
        },
    )
    await db.commit()
    return await _build_invoice_detail_response(db, inv.id)


@router.get(
    "/{invoice_id}/pdf",
    response_class=HTMLResponse,
    tags=["Invoices"],
)
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """
    Generate a clean, professional, print-ready document view of the invoice.
    Can be printed directly (Ctrl+P / window.print()) or saved to PDF.
    """
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(*_invoice_options())
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    cust = inv.customer_snapshot or {}
    addr = inv.billing_address_snapshot or {}
    company_name = cust.get("company_name", "Valued Customer")
    billing_email = cust.get("billing_email", "")
    tax_id = cust.get("tax_id", "—")
    address_line1 = addr.get("address_line1", "")
    city = addr.get("city", "")
    postal = addr.get("postal_code", "")
    country = addr.get("country", "")

    lines_html = ""
    for line in inv.lines:
        lines_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                <strong>{line.description}</strong>
                {f'<br><small style="color: #64748b;">Variant: {line.variant_name_snapshot}</small>' if line.variant_name_snapshot else ''}
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{line.quantity}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">${line.unit_price_snapshot:,.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #16a34a;">
                {f'-${line.discount_amount:,.2f}' if line.discount_amount > 0 else '—'}
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">
                ${line.tax_amount:,.2f} {f'({line.tax_rate_snapshot}%)' if line.tax_rate_snapshot else ''}
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: 600;">${line.line_total:,.2f}</td>
        </tr>
        """

    status_color = "#16a34a" if inv.status == InvoiceStatus.PAID else ("#2563eb" if inv.status == InvoiceStatus.CONFIRMED else ("#dc2626" if inv.status == InvoiceStatus.CANCELLED else "#64748b"))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Invoice {inv.invoice_number}</title>
<style>
    @page {{ size: A4; margin: 15mm; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; margin: 0; padding: 20px; }}
    .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 20px; }}
    .brand {{ font-size: 24px; font-weight: 800; color: #4338ca; }}
    .invoice-title {{ font-size: 28px; font-weight: 800; text-align: right; }}
    .status {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; text-transform: uppercase; color: white; background: {status_color}; }}
    .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 25px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 30px; }}
    th {{ background: #f8fafc; padding: 10px; text-align: left; font-size: 12px; text-transform: uppercase; color: #475569; border-bottom: 2px solid #cbd5e1; }}
    .totals {{ margin-top: 20px; margin-left: auto; width: 300px; }}
    .total-row {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; }}
    .grand-total {{ font-size: 18px; font-weight: 800; border-top: 2px solid #1e293b; padding-top: 8px; margin-top: 6px; }}
    .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 12px; }}
    @media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
</style>
</head>
<body>
<div class="no-print" style="margin-bottom: 20px; text-align: right;">
    <button onclick="window.print()" style="background: #4338ca; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: 600; cursor: pointer;">Print / Download PDF</button>
</div>
<div class="header">
    <div>
        <div class="brand">Brightloop Software Inc.</div>
        <div style="color: #64748b; font-size: 13px; margin-top: 4px;">
            100 Enterprise Way, Suite 400<br>
            San Francisco, CA 94105<br>
            Tax ID: US-94-3829102<br>
            billing@brightloop.io
        </div>
    </div>
    <div style="text-align: right;">
        <div class="invoice-title">{inv.invoice_number}</div>
        <div style="margin-top: 8px;"><span class="status">{inv.status.value}</span></div>
        <div style="margin-top: 8px; font-size: 13px; color: #64748b;">
            Issue Date: <strong>{inv.issue_date}</strong><br>
            Payment Due: <strong>{inv.due_date}</strong>
        </div>
    </div>
</div>

<div class="meta-grid">
    <div>
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b;">Billed To</div>
        <div style="font-size: 16px; font-weight: 700; margin-top: 4px;">{company_name}</div>
        <div style="color: #475569; font-size: 13px; margin-top: 2px;">
            {address_line1}<br>
            {city} {postal} {country}<br>
            Email: {billing_email}<br>
            Tax / VAT ID: {tax_id}
        </div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #64748b;">Billing Period</div>
        <div style="font-size: 15px; font-weight: 600; margin-top: 4px;">{inv.billing_period_start} &rarr; {inv.billing_period_end}</div>
        <div style="color: #64748b; font-size: 13px; margin-top: 4px;">Currency: {inv.currency}</div>
    </div>
</div>

<table>
    <thead>
        <tr>
            <th>Description</th>
            <th style="text-align: center;">Qty</th>
            <th style="text-align: right;">Unit Price</th>
            <th style="text-align: right;">Discount</th>
            <th style="text-align: right;">Tax</th>
            <th style="text-align: right;">Total</th>
        </tr>
    </thead>
    <tbody>
        {lines_html}
    </tbody>
</table>

<div class="totals">
    <div class="total-row"><span>Subtotal:</span><span>${inv.subtotal:,.2f}</span></div>
    <div class="total-row" style="color: #16a34a;"><span>Discounts Applied:</span><span>-${inv.discount_amount:,.2f}</span></div>
    <div class="total-row"><span>Taxes:</span><span>+${inv.tax_amount:,.2f}</span></div>
    <div class="total-row grand-total"><span>Total Amount:</span><span>${inv.total_amount:,.2f} {inv.currency}</span></div>
    <div class="total-row" style="color: #16a34a; font-weight: 600;"><span>Amount Paid:</span><span>${inv.paid_amount:,.2f}</span></div>
    <div class="total-row" style="font-size: 16px; font-weight: 800; color: #dc2626;"><span>Balance Due:</span><span>${inv.outstanding_balance:,.2f} {inv.currency}</span></div>
</div>

{f'<div style="margin-top: 20px; padding: 12px; background: #fee2e2; border-left: 4px solid #dc2626; border-radius: 4px; font-size: 13px;"><strong>Cancellation Reason:</strong> {inv.cancellation_reason}</div>' if inv.cancellation_reason else ''}

<div class="footer">
    Thank you for your business! Direct remittances can be transferred via ACH or Wire to Brightloop Software Inc.<br>
    Questions? Contact support@brightloop.io
</div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=200)


async def _build_invoice_detail_response(db: AsyncSession, invoice_id: uuid.UUID) -> InvoiceDetailResponse:
    query = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(*_invoice_options())
    )
    inv = (await db.execute(query)).scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    payment_responses = [
        PaymentResponse(
            id=p.id,
            invoice_id=p.invoice_id,
            amount=p.amount,
            payment_method=p.payment_method,
            payment_date=p.payment_date,
            reference_note=p.reference_note,
            is_reversed=p.is_reversed,
        )
        for p in inv.payments
    ]

    audit_query = (
        select(AuditEvent, User)
        .outerjoin(User, AuditEvent.actor_user_id == User.id)
        .where(
            AuditEvent.entity_type == "invoice",
            AuditEvent.entity_id == invoice_id,
        )
        .order_by(AuditEvent.timestamp.desc())
    )
    audit_rows = (await db.execute(audit_query)).all()

    audit_items = []
    for event, actor in audit_rows:
        audit_items.append(
            InvoiceAuditItem(
                id=event.id,
                action=event.action,
                changes=event.changes_json or {},
                actor_user_id=event.actor_user_id,
                actor_name=actor.full_name if actor else "System",
                actor_email=actor.email if actor else None,
                actor_role=actor.role.value if actor else None,
                timestamp=event.timestamp,
            )
        )

    base = _invoice_to_response(inv)
    return InvoiceDetailResponse(
        id=base.id,
        invoice_number=base.invoice_number,
        subscription_id=base.subscription_id,
        customer_account_id=base.customer_account_id,
        customer_name=base.customer_name,
        currency=base.currency,
        status=base.status,
        billing_period_start=base.billing_period_start,
        billing_period_end=base.billing_period_end,
        subtotal=base.subtotal,
        tax_amount=base.tax_amount,
        discount_amount=base.discount_amount,
        total_amount=base.total_amount,
        paid_amount=base.paid_amount,
        outstanding_balance=base.outstanding_balance,
        is_overdue=base.is_overdue,
        issue_date=base.issue_date,
        due_date=base.due_date,
        send_status=base.send_status,
        lines=base.lines,
        customer_snapshot=inv.customer_snapshot or {},
        billing_address_snapshot=inv.billing_address_snapshot or {},
        cancellation_reason=inv.cancellation_reason,
        sent_at=inv.sent_at,
        payments=payment_responses,
        audit_history=audit_items,
    )
