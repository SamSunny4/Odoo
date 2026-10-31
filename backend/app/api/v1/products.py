from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.catalog import Product
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.catalog import ProductResponse, PlanResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get(
    "/products",
    response_model=Union[PaginatedResponse[ProductResponse], List[ProductResponse]],
    tags=["Catalog"],
)
async def list_products(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for product name or type"),
    type: Optional[str] = Query(None, description="Filter by product type"),
    sort_by: Optional[str] = Query("name", description="Sort by: name, sales_price, type, created_at"),
    sort_order: Optional[str] = Query("asc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """
    List active products and their variants with server-side search, filtering, sorting, and pagination.
    Restricts cost price visibility: only Admin can see cost_price; hidden for Staff and Customers.
    Emits pagination headers (X-Total-Count, X-Page, X-Page-Size, X-Total-Pages).
    """
    query = (
        select(Product)
        .where(Product.is_active == True)  # noqa: E712
        .options(selectinload(Product.variants))
    )
    count_query = (
        select(func.count(Product.id))
        .where(Product.is_active == True)  # noqa: E712
    )

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Product.name.ilike(term),
                Product.type.ilike(term),
                Product.notes.ilike(term),
            )
        )

    if type and type.strip():
        filters.append(Product.type.ilike(type.strip()))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_count = (await db.execute(count_query)).scalar_one()

    # Sorting
    sort_col = Product.name
    if sort_by == "sales_price":
        sort_col = Product.sales_price
    elif sort_by == "type":
        sort_col = Product.type
    elif sort_by == "created_at":
        sort_col = Product.created_at

    if sort_order and sort_order.lower() == "desc":
        query = query.order_by(sort_col.desc().nulls_last())
    else:
        query = query.order_by(sort_col.asc().nulls_last())

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Pages"] = str(total_pages)

    is_admin = current_user is not None and current_user.role == UserRole.ADMIN

    response_items = []
    for p in products:
        prod_dict = ProductResponse.model_validate(p)
        if not is_admin:
            prod_dict.cost_price = None  # Hide sensitive cost price
        response_items.append(prod_dict)

    if envelope:
        return PaginatedResponse[ProductResponse](
            items=response_items,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    return response_items


@router.get("/plans", response_model=List[PlanResponse], tags=["Catalog"])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all active subscription plans."""
    query = select(Plan).where(Plan.is_active == True)  # noqa: E712
    result = await db.execute(query)
    plans = result.scalars().all()
    return [PlanResponse.model_validate(plan) for plan in plans]
