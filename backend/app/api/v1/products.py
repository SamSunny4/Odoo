import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.catalog import Product, ProductVariant, ProductType
from app.models.plan import Plan, BillingCadence
from app.models.tax import TaxRule
from app.models.discount import DiscountRule, DiscountScope, DiscountType, DiscountRedemption
from app.models.user import User, UserRole
from app.schemas.catalog import (
    ProductResponse,
    ProductCreate,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantResponse,
    PlanResponse,
    PlanCreate,
    PlanUpdate,
    CalculatePreviewRequest,
    CalculatePreviewResponse,
    CalculatePreviewLineResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import get_current_user, require_admin
from app.services.audit import record_audit_event

CENT = Decimal("0.01")


def _money(val: Decimal) -> Decimal:
    return val.quantize(CENT, rounding=ROUND_HALF_UP)


router = APIRouter()


# -----------------------------------------------------------------------------
# Products & Variants
# -----------------------------------------------------------------------------

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
    include_inactive: bool = Query(False, description="Include archived/inactive products (admin only)"),
    sort_by: Optional[str] = Query("name", description="Sort by: name, sales_price, type, created_at"),
    sort_order: Optional[str] = Query("asc", description="Sort direction: asc or desc"),
    envelope: bool = Query(False, description="Return wrapped object with pagination metadata"),
):
    """
    List active products and their variants with server-side search, filtering, sorting, and pagination.
    Restricts cost price visibility: only Admin can see cost_price; hidden for Staff and Customers.
    """
    is_admin = current_user is not None and current_user.role == UserRole.ADMIN

    query = select(Product).options(selectinload(Product.variants))
    count_query = select(func.count(Product.id))

    if not (include_inactive and is_admin):
        query = query.where(Product.is_active == True)  # noqa: E712
        count_query = count_query.where(Product.is_active == True)  # noqa: E712

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Product.name.ilike(term),
                Product.notes.ilike(term),
            )
        )

    if type and type.strip():
        try:
            ptype = ProductType(type.strip().lower())
            filters.append(Product.type == ptype)
        except ValueError:
            pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_count = (await db.execute(count_query)).scalar_one()

    # Sorting
    sort_col = Product.name
    if sort_by == "sales_price":
        sort_col = Product.sales_price
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


@router.get("/products/{product_id}", response_model=ProductResponse, tags=["Catalog"])
async def get_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Retrieve details for a single product and its variants."""
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants))
    )
    product = (await db.execute(query)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    is_admin = current_user is not None and current_user.role == UserRole.ADMIN
    prod_resp = ProductResponse.model_validate(product)
    if not is_admin:
        prod_resp.cost_price = None
    return prod_resp


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Catalog"],
)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Create a new product with optional initial variants.
    Strictly restricted to Administrator role.
    """
    product = Product(
        name=payload.name.strip(),
        type=payload.type,
        sales_price=payload.sales_price,
        cost_price=payload.cost_price,
        notes=payload.notes,
        is_add_on=payload.is_add_on,
        is_active=payload.is_active,
    )
    db.add(product)
    await db.flush()

    if payload.variants:
        for v in payload.variants:
            variant = ProductVariant(
                product_id=product.id,
                name=v.name.strip(),
                price_adjustment=v.price_adjustment,
                is_active=v.is_active,
            )
            db.add(variant)
        await db.flush()

    await record_audit_event(
        db,
        entity_type="product",
        entity_id=product.id,
        action="CREATE_PRODUCT",
        actor_user_id=current_admin.id,
        changes={
            "name": product.name,
            "type": product.type.value,
            "sales_price": str(product.sales_price),
            "cost_price": str(product.cost_price),
            "is_add_on": product.is_add_on,
            "variants_count": len(payload.variants) if payload.variants else 0,
        },
    )

    await db.commit()
    await db.refresh(product, ["variants"])
    return ProductResponse.model_validate(product)


@router.put("/products/{product_id}", response_model=ProductResponse, tags=["Catalog"])
@router.patch("/products/{product_id}", response_model=ProductResponse, tags=["Catalog"])
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update product details. Strictly restricted to Administrator role."""
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.variants))
    )
    product = (await db.execute(query)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    if payload.sales_price is not None:
        if any(
            variant.is_active
            and payload.sales_price + Decimal(str(variant.price_adjustment)) < 0
            for variant in product.variants
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The new sales price would make an active variant price negative.",
            )

    changes = {}
    if payload.name is not None and payload.name.strip() != product.name:
        changes["name"] = {"from": product.name, "to": payload.name.strip()}
        product.name = payload.name.strip()

    if payload.type is not None and payload.type != product.type:
        changes["type"] = {"from": product.type.value, "to": payload.type.value}
        product.type = payload.type

    if payload.sales_price is not None and payload.sales_price != product.sales_price:
        changes["sales_price"] = {"from": str(product.sales_price), "to": str(payload.sales_price)}
        product.sales_price = payload.sales_price

    if payload.cost_price is not None and payload.cost_price != product.cost_price:
        changes["cost_price"] = {"from": str(product.cost_price), "to": str(payload.cost_price)}
        product.cost_price = payload.cost_price

    if payload.notes is not None and payload.notes != product.notes:
        changes["notes"] = {"from": product.notes, "to": payload.notes}
        product.notes = payload.notes

    if payload.is_add_on is not None and payload.is_add_on != product.is_add_on:
        changes["is_add_on"] = {"from": product.is_add_on, "to": payload.is_add_on}
        product.is_add_on = payload.is_add_on

    if payload.is_active is not None and payload.is_active != product.is_active:
        changes["is_active"] = {"from": product.is_active, "to": payload.is_active}
        product.is_active = payload.is_active

    if changes:
        await record_audit_event(
            db,
            entity_type="product",
            entity_id=product.id,
            action="UPDATE_PRODUCT",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(product, ["variants"])

    return ProductResponse.model_validate(product)


@router.delete("/products/{product_id}", tags=["Catalog"])
async def archive_product(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Archive a product so it cannot be added to new quotes. Admin only."""
    query = select(Product).where(Product.id == product_id)
    product = (await db.execute(query)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    product.is_active = False
    await record_audit_event(
        db,
        entity_type="product",
        entity_id=product.id,
        action="ARCHIVE_PRODUCT",
        actor_user_id=current_admin.id,
        changes={"is_active": False},
    )
    await db.commit()
    return {"message": f"Product '{product.name}' archived successfully.", "is_active": False}


# -----------------------------------------------------------------------------
# Product Variants CRUD
# -----------------------------------------------------------------------------

@router.get(
    "/products/{product_id}/variants",
    response_model=List[ProductVariantResponse],
    tags=["Catalog"],
)
async def list_product_variants(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    include_inactive: bool = Query(False),
):
    """List all variants for a given product."""
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    query = select(ProductVariant).where(ProductVariant.product_id == product_id)
    if not include_inactive:
        query = query.where(ProductVariant.is_active == True)
    query = query.order_by(ProductVariant.name.asc())

    variants = (await db.execute(query)).scalars().all()
    return [ProductVariantResponse.model_validate(v) for v in variants]


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Catalog"],
)
async def create_product_variant(
    product_id: uuid.UUID,
    payload: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Add a variant with price adjustment to an existing product. Admin only."""
    product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    if Decimal(str(product.sales_price)) + payload.price_adjustment < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A variant price adjustment cannot make the product price negative.",
        )

    variant = ProductVariant(
        product_id=product_id,
        name=payload.name.strip(),
        price_adjustment=payload.price_adjustment,
        is_active=payload.is_active,
    )
    db.add(variant)
    await db.flush()

    await record_audit_event(
        db,
        entity_type="product_variant",
        entity_id=variant.id,
        action="CREATE_VARIANT",
        actor_user_id=current_admin.id,
        changes={
            "product_id": str(product_id),
            "name": variant.name,
            "price_adjustment": str(variant.price_adjustment),
        },
    )

    await db.commit()
    await db.refresh(variant)
    return ProductVariantResponse.model_validate(variant)


@router.put(
    "/products/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
    tags=["Catalog"],
)
@router.patch(
    "/products/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
    tags=["Catalog"],
)
async def update_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: ProductVariantUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update a product variant. Admin only."""
    query = select(ProductVariant).where(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == product_id,
    )
    variant = (await db.execute(query)).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found.")

    if payload.price_adjustment is not None:
        product = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
        if Decimal(str(product.sales_price)) + payload.price_adjustment < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A variant price adjustment cannot make the product price negative.",
            )

    changes = {}
    if payload.name is not None and payload.name.strip() != variant.name:
        changes["name"] = {"from": variant.name, "to": payload.name.strip()}
        variant.name = payload.name.strip()

    if payload.price_adjustment is not None and payload.price_adjustment != variant.price_adjustment:
        changes["price_adjustment"] = {"from": str(variant.price_adjustment), "to": str(payload.price_adjustment)}
        variant.price_adjustment = payload.price_adjustment

    if payload.is_active is not None and payload.is_active != variant.is_active:
        changes["is_active"] = {"from": variant.is_active, "to": payload.is_active}
        variant.is_active = payload.is_active

    if changes:
        await record_audit_event(
            db,
            entity_type="product_variant",
            entity_id=variant.id,
            action="UPDATE_VARIANT",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(variant)

    return ProductVariantResponse.model_validate(variant)


@router.delete("/products/{product_id}/variants/{variant_id}", tags=["Catalog"])
async def archive_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Archive a product variant so it cannot be selected on new quotes. Admin only."""
    query = select(ProductVariant).where(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == product_id,
    )
    variant = (await db.execute(query)).scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found.")

    variant.is_active = False
    await record_audit_event(
        db,
        entity_type="product_variant",
        entity_id=variant.id,
        action="ARCHIVE_VARIANT",
        actor_user_id=current_admin.id,
        changes={"is_active": False},
    )
    await db.commit()
    return {"message": f"Variant '{variant.name}' archived successfully.", "is_active": False}


# -----------------------------------------------------------------------------
# Plans CRUD
# -----------------------------------------------------------------------------

@router.get(
    "/plans",
    response_model=Union[PaginatedResponse[PlanResponse], List[PlanResponse]],
    tags=["Catalog"],
)
async def list_plans(
    response: Response,
    db: AsyncSession = Depends(get_db),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    search: Optional[str] = Query(None),
    cadence: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    envelope: bool = Query(False),
):
    """List subscription plans with search, filtering, and optional pagination."""
    query = select(Plan)
    count_query = select(func.count(Plan.id))

    if not include_inactive:
        query = query.where(Plan.is_active == True)  # noqa: E712
        count_query = count_query.where(Plan.is_active == True)  # noqa: E712

    filters = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(Plan.name.ilike(term))

    if cadence and cadence.strip():
        try:
            bcad = BillingCadence(cadence.strip().lower())
            filters.append(Plan.cadence == bcad)
        except ValueError:
            pass

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    query = query.order_by(Plan.created_at.desc())

    total_count = (await db.execute(count_query)).scalar_one()

    # Apply pagination only when page/page_size or envelope requested
    if page is not None or page_size is not None or envelope:
        p = page or 1
        ps = page_size or 10
        total_pages = (total_count + ps - 1) // ps if total_count > 0 else 1
        query = query.offset((p - 1) * ps).limit(ps)

        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Page"] = str(p)
        response.headers["X-Page-Size"] = str(ps)
        response.headers["X-Total-Pages"] = str(total_pages)
    else:
        response.headers["X-Total-Count"] = str(total_count)
        p = 1
        ps = total_count
        total_pages = 1

    result = await db.execute(query)
    plans = result.scalars().all()
    items = [PlanResponse.model_validate(plan) for plan in plans]

    if envelope:
        return PaginatedResponse[PlanResponse](
            items=items,
            total=total_count,
            page=p,
            page_size=ps,
            total_pages=total_pages,
        )

    return items


@router.get("/plans/{plan_id}", response_model=PlanResponse, tags=["Catalog"])
async def get_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve details for a single plan."""
    query = select(Plan).where(Plan.id == plan_id)
    plan = (await db.execute(query)).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return PlanResponse.model_validate(plan)


@router.post(
    "/plans",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Catalog"],
)
async def create_plan(
    payload: PlanCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Create a new subscription plan.
    Validates price, minimum quantity, availability dates, and lifecycle policies.
    Admin only.
    """
    plan = Plan(
        name=payload.name.strip(),
        cadence=payload.cadence,
        base_price=payload.base_price,
        min_quantity=payload.min_quantity,
        available_from=payload.available_from,
        available_to=payload.available_to,
        auto_close_on_expiry=payload.auto_close_on_expiry,
        allow_early_close=payload.allow_early_close,
        allow_pause=payload.allow_pause,
        allow_renewal=payload.allow_renewal,
        is_active=payload.is_active,
    )
    db.add(plan)
    await db.flush()

    await record_audit_event(
        db,
        entity_type="plan",
        entity_id=plan.id,
        action="CREATE_PLAN",
        actor_user_id=current_admin.id,
        changes={
            "name": plan.name,
            "cadence": plan.cadence.value,
            "base_price": str(plan.base_price),
            "min_quantity": plan.min_quantity,
        },
    )

    await db.commit()
    await db.refresh(plan)
    return PlanResponse.model_validate(plan)


@router.put("/plans/{plan_id}", response_model=PlanResponse, tags=["Catalog"])
@router.patch("/plans/{plan_id}", response_model=PlanResponse, tags=["Catalog"])
async def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update subscription plan policies or pricing. Admin only."""
    query = select(Plan).where(Plan.id == plan_id)
    plan = (await db.execute(query)).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

    supplied = payload.model_fields_set
    nullable_fields = {"available_from", "available_to"}
    for field_name in supplied - nullable_fields:
        if getattr(payload, field_name) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} cannot be null.",
            )

    proposed_from = payload.available_from if "available_from" in supplied else plan.available_from
    proposed_to = payload.available_to if "available_to" in supplied else plan.available_to
    proposed_auto_close = (
        payload.auto_close_on_expiry
        if "auto_close_on_expiry" in supplied
        else plan.auto_close_on_expiry
    )
    proposed_renewal = payload.allow_renewal if "allow_renewal" in supplied else plan.allow_renewal
    if proposed_from and proposed_to and proposed_from > proposed_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="available_from date cannot be after available_to date.",
        )
    if not proposed_renewal and not proposed_auto_close:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A plan that disallows renewal must automatically close on expiry.",
        )

    changes = {}
    for field_name in supplied:
        new_value = getattr(payload, field_name)
        old_value = getattr(plan, field_name)
        if field_name == "name":
            new_value = new_value.strip()
            if not new_value:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="name cannot be blank.",
                )
        if new_value == old_value:
            continue
        audit_old = old_value.value if hasattr(old_value, "value") else old_value
        audit_new = new_value.value if hasattr(new_value, "value") else new_value
        if isinstance(audit_old, (date,)):
            audit_old = audit_old.isoformat()
        if isinstance(audit_new, (date,)):
            audit_new = audit_new.isoformat()
        if isinstance(audit_old, Decimal):
            audit_old = str(audit_old)
        if isinstance(audit_new, Decimal):
            audit_new = str(audit_new)
        changes[field_name] = {"from": audit_old, "to": audit_new}
        setattr(plan, field_name, new_value)

    if changes:
        await record_audit_event(
            db,
            entity_type="plan",
            entity_id=plan.id,
            action="UPDATE_PLAN",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(plan)

    return PlanResponse.model_validate(plan)


@router.delete("/plans/{plan_id}", tags=["Catalog"])
async def archive_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Archive a plan so it cannot be chosen for new subscriptions. Admin only."""
    query = select(Plan).where(Plan.id == plan_id)
    plan = (await db.execute(query)).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

    plan.is_active = False
    await record_audit_event(
        db,
        entity_type="plan",
        entity_id=plan.id,
        action="ARCHIVE_PLAN",
        actor_user_id=current_admin.id,
        changes={"is_active": False},
    )
    await db.commit()
    return {"message": f"Plan '{plan.name}' archived successfully.", "is_active": False}


# -----------------------------------------------------------------------------
# Price Calculation & Quote Preview
# -----------------------------------------------------------------------------

@router.post(
    "/catalog/calculate-preview",
    response_model=CalculatePreviewResponse,
    tags=["Catalog"],
)
async def calculate_preview(
    payload: CalculatePreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate exact totals for any plan, product variants, tax, and discount combination.
    Demonstrates exact price adjustments (e.g. +560 for Odoo brand) and currency-aware rounding.
    """
    as_of = payload.as_of or date.today()
    warnings = []
    lines_output: List[CalculatePreviewLineResponse] = []
    line_product_ids: List[Optional[uuid.UUID]] = []
    line_tax_rule_ids: List[Optional[uuid.UUID]] = []
    line_quantities: List[int] = []

    plan_name = None
    plan_base_price = Decimal("0.00")

    # 1. Plan line (if selected)
    if payload.plan_id:
        plan_obj = (await db.execute(select(Plan).where(Plan.id == payload.plan_id))).scalar_one_or_none()
        if not plan_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
        if not plan_obj.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected plan is archived and unavailable for new sales.",
            )
        if plan_obj.available_from and as_of < plan_obj.available_from:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plan is not yet available (starts {plan_obj.available_from}).",
            )
        if plan_obj.available_to and as_of > plan_obj.available_to:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plan availability expired on {plan_obj.available_to}.",
            )

        plan_name = plan_obj.name
        plan_base_price = _money(Decimal(str(plan_obj.base_price)))
        lines_output.append(
            CalculatePreviewLineResponse(
                description=f"Plan Base Fee — {plan_obj.name}",
                product_name=plan_obj.name,
                variant_name=None,
                price_adjustment=Decimal("0.00"),
                unit_price=plan_base_price,
                quantity=1,
                subtotal=plan_base_price,
                discount_amount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                line_total=plan_base_price,
            )
        )
        line_product_ids.append(None)
        line_tax_rule_ids.append(payload.default_tax_rule_id)
        line_quantities.append(0)

    # 2. Product lines with variant price adjustments
    total_qty = 0
    for req_line in payload.product_lines:
        prod = (await db.execute(select(Product).where(Product.id == req_line.product_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
        if not prod.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product '{prod.name}' is archived and unavailable for new sales.",
            )

        base_unit = Decimal(str(prod.sales_price))
        adjustment = Decimal("0.00")
        variant_name = None

        if req_line.variant_id:
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == req_line.variant_id,
                        ProductVariant.product_id == prod.id,
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant {req_line.variant_id} does not belong to product '{prod.name}'.",
                )
            if not variant.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Variant '{variant.name}' is archived and unavailable for new sales.",
                )
            adjustment = Decimal(str(variant.price_adjustment))
            variant_name = variant.name

        unit_price = _money(base_unit + adjustment)
        if unit_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The selected variant makes '{prod.name}' price negative.",
            )
        qty = req_line.quantity
        subtotal = _money(unit_price * qty)
        total_qty += qty

        desc = f"{prod.name} ({variant_name})" if variant_name else prod.name

        lines_output.append(
            CalculatePreviewLineResponse(
                description=desc,
                product_name=prod.name,
                variant_name=variant_name,
                price_adjustment=adjustment,
                unit_price=unit_price,
                quantity=qty,
                subtotal=subtotal,
                discount_amount=Decimal("0.00"),
                tax_rate=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
                line_total=subtotal,
            )
        )
        line_product_ids.append(prod.id)
        line_tax_rule_ids.append(req_line.tax_rule_id or payload.default_tax_rule_id)
        line_quantities.append(qty)

    gross_subtotal = sum((l.subtotal for l in lines_output), Decimal("0.00"))
    if payload.plan_id and plan_obj and total_qty < plan_obj.min_quantity:
        warnings.append(f"Quantity {total_qty} is below the plan minimum of {plan_obj.min_quantity}.")

    # 3. Discount evaluation
    discount_amount = Decimal("0.00")
    discount_name = None

    if payload.discount_rule_id:
        disc = (
            await db.execute(select(DiscountRule).where(DiscountRule.id == payload.discount_rule_id))
        ).scalar_one_or_none()

        if not disc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found.")
        discount_name = disc.name
        eligible_indices: List[int] = []
        if disc.scope == DiscountScope.SUBSCRIPTION:
            eligible_indices = list(range(len(lines_output)))
        elif disc.scope == DiscountScope.PRODUCT and disc.target_product_id:
            eligible_indices = [
                index for index, product_id in enumerate(line_product_ids)
                if product_id == disc.target_product_id
            ]

        eligible_subtotal = sum((lines_output[i].subtotal for i in eligible_indices), Decimal("0.00"))
        eligible_qty = sum(line_quantities[i] for i in eligible_indices)
        if not disc.is_active:
            warnings.append(f"Discount '{disc.name}' is currently inactive.")
        elif not (disc.valid_from <= as_of <= disc.valid_to):
            warnings.append(
                f"Discount '{disc.name}' is outside its active validity window ({disc.valid_from} to {disc.valid_to})."
            )
        else:
            used_count = (await db.execute(
                select(func.count(DiscountRedemption.id)).where(
                    DiscountRedemption.discount_rule_id == disc.id
                )
            )).scalar_one()
            if disc.max_usage_limit is not None and used_count >= disc.max_usage_limit:
                warnings.append(
                    f"Discount '{disc.name}' has reached its maximum usage cap ({disc.max_usage_limit})."
                )
            elif not eligible_indices:
                warnings.append(f"Discount '{disc.name}' has no eligible lines in this preview.")
            elif eligible_subtotal < disc.min_spend:
                warnings.append(f"Subtotal ${eligible_subtotal} is below discount min spend ${disc.min_spend}.")
            elif eligible_qty < disc.min_quantity:
                warnings.append(f"Quantity {eligible_qty} is below discount min quantity {disc.min_quantity}.")
            elif disc.discount_type == DiscountType.PERCENTAGE:
                discount_amount = _money(eligible_subtotal * Decimal(str(disc.value)) / Decimal("100"))
            else:
                discount_amount = min(eligible_subtotal, Decimal(str(disc.value)))

        # Allocate only across the lines eligible for this rule.
        remaining_discount = discount_amount
        for position, line_index in enumerate(eligible_indices):
            line = lines_output[line_index]
            if position == len(eligible_indices) - 1:
                allocation = remaining_discount
            elif eligible_subtotal > 0:
                allocation = _money(discount_amount * line.subtotal / eligible_subtotal)
            else:
                allocation = Decimal("0.00")
            allocation = min(line.subtotal, max(Decimal("0.00"), allocation), remaining_discount)
            line.discount_amount = allocation
            remaining_discount -= allocation

    # 4. Tax evaluation
    tax_rules_cache = {}
    tax_amount = Decimal("0.00")

    for i, l in enumerate(lines_output):
        req_tax_id = line_tax_rule_ids[i]
        if req_tax_id:
            if req_tax_id not in tax_rules_cache:
                t_rule = (await db.execute(select(TaxRule).where(TaxRule.id == req_tax_id))).scalar_one_or_none()
                tax_rules_cache[req_tax_id] = t_rule
            t_rule = tax_rules_cache[req_tax_id]

            if t_rule and t_rule.is_active:
                l.tax_rate = Decimal(str(t_rule.rate_percentage))
                taxable_base = max(Decimal("0.00"), l.subtotal - l.discount_amount)
                l.tax_amount = _money(taxable_base * l.tax_rate / Decimal("100"))
                tax_amount += l.tax_amount
            else:
                warnings.append(f"Tax rule for '{l.description}' is inactive or missing.")

        l.line_total = _money(l.subtotal - l.discount_amount + l.tax_amount)

    discount_amount = sum((line.discount_amount for line in lines_output), Decimal("0.00"))
    total_amount = sum((line.line_total for line in lines_output), Decimal("0.00"))

    return CalculatePreviewResponse(
        plan_name=plan_name,
        plan_base_price=plan_base_price,
        lines=lines_output,
        subtotal=gross_subtotal,
        discount_amount=discount_amount,
        discount_name=discount_name,
        tax_amount=tax_amount,
        total_amount=total_amount,
        warnings=warnings,
    )
