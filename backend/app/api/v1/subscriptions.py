import uuid
from typing import List, Optional, Union
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.customer import CustomerAccount
from app.models.plan import Plan
from app.models.catalog import Product, ProductVariant
from app.schemas.subscription import SubscriptionResponse, SubscriptionLineResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get(
    "",
    response_model=Union[PaginatedResponse[SubscriptionResponse], List[SubscriptionResponse]],
    tags=["Subscriptions"],
)
async def list_subscriptions(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for subscription # or customer name"),
    status: Optional[str] = Query(None, description="Filter by status: active, quotation, paused, closed, draft"),
    sort_by: Optional[str] = Query("created_at", description="Field to sort by: created_at, subscription_number, start_date, next_billing_date"),
    sort_order: Optional[str] = Query("desc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """
    List subscriptions for admin/staff operations with server-side search, filtering, sorting, and pagination.
    Emits pagination headers (X-Total-Count, X-Page, X-Page-Size, X-Total-Pages).
    """
    query = (
        select(Subscription)
        .outerjoin(CustomerAccount, Subscription.customer_account_id == CustomerAccount.id)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
    )
    count_query = (
        select(func.count(distinct(Subscription.id)))
        .select_from(Subscription)
        .outerjoin(CustomerAccount, Subscription.customer_account_id == CustomerAccount.id)
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Subscription.subscription_number.ilike(term),
                CustomerAccount.company_name.ilike(term),
            )
        )

    if status and status.strip():
        try:
            status_enum = SubscriptionStatus(status.strip().lower())
            filters.append(Subscription.status == status_enum)
        except ValueError:
            pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    # Total matching records
    total_count = (await db.execute(count_query)).scalar_one()

    # Sorting
    sort_col = Subscription.created_at
    if sort_by == "subscription_number":
        sort_col = Subscription.subscription_number
    elif sort_by == "start_date":
        sort_col = Subscription.start_date
    elif sort_by == "expiry_date":
        sort_col = Subscription.expiry_date
    elif sort_by == "next_billing_date":
        sort_col = Subscription.next_billing_date

    if sort_order and sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(sort_col.desc().nulls_last())

    # Pagination slice
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    subscriptions = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    # Emit pagination headers for client inspection
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    items = []
    for sub in subscriptions:
        total = Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00")
        line_responses = []
        for line in sub.lines:
            line_price = Decimal(str(line.unit_price)) * line.quantity
            total += line_price
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
                customer_name=sub.customer_account.company_name if sub.customer_account else "Unknown",
                plan_id=sub.plan_id,
                plan_name=sub.plan.name if sub.plan else "Unknown",
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


@router.post("/{subscription_id}/pause", tags=["Subscriptions"])
async def pause_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Pause an active subscription if plan policy permits."""
    query = select(Subscription).where(Subscription.id == subscription_id).options(selectinload(Subscription.plan))
    sub = (await db.execute(query)).scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if sub.status != SubscriptionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Only active subscriptions can be paused.")
    if sub.plan and not sub.plan.allow_pause:
        raise HTTPException(status_code=400, detail="Plan policy does not permit pausing.")

    sub.status = SubscriptionStatus.PAUSED
    await record_audit_event(
        db,
        entity_type="subscription",
        entity_id=sub.id,
        action="PAUSE",
        actor_user_id=_user.id,
        changes={"subscription_number": sub.subscription_number, "status": sub.status.value},
    )
    await db.commit()
    return {"message": f"Subscription {sub.subscription_number} has been paused.", "status": sub.status}


@router.post("/{subscription_id}/resume", tags=["Subscriptions"])
async def resume_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Resume a paused subscription."""
    query = select(Subscription).where(Subscription.id == subscription_id)
    sub = (await db.execute(query)).scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found.")
    if sub.status != SubscriptionStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Only paused subscriptions can be resumed.")

    sub.status = SubscriptionStatus.ACTIVE
    await record_audit_event(
        db,
        entity_type="subscription",
        entity_id=sub.id,
        action="RESUME",
        actor_user_id=_user.id,
        changes={"subscription_number": sub.subscription_number, "status": sub.status.value},
    )
    await db.commit()
    return {"message": f"Subscription {sub.subscription_number} has been resumed.", "status": sub.status}
