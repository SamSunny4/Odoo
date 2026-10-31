import uuid
from typing import List, Optional, Union
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from app.models.customer import CustomerAccount
from app.schemas.invoice import InvoiceResponse, InvoiceLineResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event

router = APIRouter()


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
    status: Optional[str] = Query(None, description="Filter by status: draft, confirmed, paid, canceled, or 'overdue'"),
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
        .options(
            selectinload(Invoice.customer_account),
            selectinload(Invoice.lines),
        )
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
            try:
                status_enum = InvoiceStatus(s)
                filters.append(Invoice.status == status_enum)
            except ValueError:
                pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    # Total count
    total_count = (await db.execute(count_query)).scalar_one()

    # Sorting
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

    # Pagination slice
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    invoices = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    # Emit pagination headers
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    items = []
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

        items.append(
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

    if envelope:
        return PaginatedResponse[InvoiceResponse](
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return items


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
