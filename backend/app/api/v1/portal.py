from typing import List, Optional, Union
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.user import User
from app.models.customer import CustomerAccount, CustomerAccountMembership
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.schemas.subscription import SubscriptionResponse, SubscriptionLineResponse
from app.schemas.invoice import InvoiceResponse, InvoiceLineResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_customer

router = APIRouter()


async def _get_customer_account_id(user: User, db: AsyncSession):
    """Derive customer account strictly from user's authenticated session membership."""
    query = select(CustomerAccountMembership).where(CustomerAccountMembership.user_id == user.id)
    membership = (await db.execute(query)).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No customer account associated with this user.",
        )
    return membership.customer_account_id


@router.get(
    "/subscriptions",
    response_model=Union[PaginatedResponse[SubscriptionResponse], List[SubscriptionResponse]],
    tags=["Customer Portal"],
)
async def get_my_subscriptions(
    response: Response,
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for subscription #"),
    status: Optional[str] = Query(None, description="Filter by status: active, quotation, paused, closed"),
    sort_by: Optional[str] = Query("created_at", description="Sort by: created_at, subscription_number, start_date"),
    sort_order: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """Exposes only the signed-in customer's subscriptions with server-side pagination, search, and sorting."""
    account_id = await _get_customer_account_id(customer_user, db)

    query = (
        select(Subscription)
        .where(Subscription.customer_account_id == account_id)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )
    count_query = (
        select(func.count(Subscription.id))
        .where(Subscription.customer_account_id == account_id)
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(Subscription.subscription_number.ilike(term))

    if status and status.strip():
        try:
            status_enum = SubscriptionStatus(status.strip().lower())
            filters.append(Subscription.status == status_enum)
        except ValueError:
            pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_count = (await db.execute(count_query)).scalar_one()

    # Sorting
    sort_col = Subscription.created_at
    if sort_by == "subscription_number":
        sort_col = Subscription.subscription_number
    elif sort_by == "start_date":
        sort_col = Subscription.start_date
    elif sort_by == "next_billing_date":
        sort_col = Subscription.next_billing_date

    if sort_order and sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(sort_col.desc().nulls_last())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    subs = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    items = []
    for sub in subs:
        total = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        line_responses = []
        for line in sub.lines:
            total += Decimal(str(line.unit_price)) * line.quantity
            line_responses.append(
                SubscriptionLineResponse(
                    id=line.id,
                    product_id=line.product_id,
                    product_name=line.product.name if line.product else "Product",
                    variant_name=line.variant.name if line.variant else None,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
            )

        items.append(
            SubscriptionResponse(
                id=sub.id,
                subscription_number=sub.subscription_number,
                customer_account_id=sub.customer_account_id,
                customer_name=sub.customer_account.company_name if sub.customer_account else "My Company",
                plan_id=sub.plan_id,
                plan_name=sub.plan.name if sub.plan else "Plan",
                status=sub.status,
                start_date=sub.start_date,
                expiry_date=sub.expiry_date,
                next_billing_date=sub.next_billing_date,
                billing_anchor_day=sub.billing_anchor_day,
                payment_terms_days=sub.payment_terms_days,
                total_amount=total,
                lines=line_responses,
            )
        )

    if envelope:
        return PaginatedResponse[SubscriptionResponse](
            items=items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return items


@router.get(
    "/invoices",
    response_model=Union[PaginatedResponse[InvoiceResponse], List[InvoiceResponse]],
    tags=["Customer Portal"],
)
async def get_my_invoices(
    response: Response,
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for invoice #"),
    status: Optional[str] = Query(None, description="Filter by status: draft, confirmed, paid, cancelled, overdue"),
    sort_by: Optional[str] = Query("issue_date", description="Sort by: issue_date, due_date, total_amount, invoice_number"),
    sort_order: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """Exposes only the signed-in customer's invoices with server-side pagination, search, and sorting."""
    account_id = await _get_customer_account_id(customer_user, db)

    query = (
        select(Invoice)
        .where(Invoice.customer_account_id == account_id)
        .options(
            selectinload(Invoice.customer_account),
            selectinload(Invoice.lines),
        )
    )
    count_query = (
        select(func.count(Invoice.id))
        .where(Invoice.customer_account_id == account_id)
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(Invoice.invoice_number.ilike(term))

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

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    invoices = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

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
                customer_name=inv.customer_account.company_name if inv.customer_account else "My Company",
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


@router.get("/profile", tags=["Customer Portal"])
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    customer_user: User = Depends(require_customer),
):
    """Returns company profile and billing details for the authenticated customer."""
    account_id = await _get_customer_account_id(customer_user, db)
    query = select(CustomerAccount).where(CustomerAccount.id == account_id)
    account = (await db.execute(query)).scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Customer account record not found.")

    return {
        "company_name": account.company_name,
        "billing_email": account.billing_email,
        "phone": account.phone,
        "tax_id": account.tax_id,
        "billing_address": f"{account.billing_address_line1}, {account.billing_city}, {account.billing_state or ''} {account.billing_postal_code}, {account.billing_country}",
        "currency": account.currency,
    }
