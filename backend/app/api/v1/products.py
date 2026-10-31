from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.catalog import Product
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.catalog import ProductResponse, PlanResponse
from app.api.v1.deps import get_current_user

router = APIRouter()


@router.get("/products", response_model=List[ProductResponse], tags=["Catalog"])
async def list_products(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    List all active products and their variants.
    Restricts cost price visibility: only Admin can see cost_price; hidden for Staff and Customers.
    """
    query = select(Product).where(Product.is_active == True).options(selectinload(Product.variants))  # noqa: E712
    result = await db.execute(query)
    products = result.scalars().all()

    is_admin = current_user is not None and current_user.role == UserRole.ADMIN

    response_items = []
    for p in products:
        prod_dict = ProductResponse.model_validate(p)
        if not is_admin:
            prod_dict.cost_price = None  # Hide sensitive cost price
        response_items.append(prod_dict)

    return response_items


@router.get("/plans", response_model=List[PlanResponse], tags=["Catalog"])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """List all active subscription plans."""
    query = select(Plan).where(Plan.is_active == True)  # noqa: E712
    result = await db.execute(query)
    plans = result.scalars().all()
    return [PlanResponse.model_validate(plan) for plan in plans]

