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

    changes = {}
    if payload.name is not None and payload.name.strip() != plan.name:
        changes["name"] = {"from": plan.name, "to": payload.name.strip()}
        plan.name = payload.name.strip()

    if payload.cadence is not None and payload.cadence != plan.cadence:
        changes["cadence"] = {"from": plan.cadence.value, "to": payload.cadence.value}
        plan.cadence = payload.cadence

    if payload.base_price is not None and payload.base_price != plan.base_price:
        changes["base_price"] = {"from": str(plan.base_price), "to": str(payload.base_price)}
        plan.base_price = payload.base_price

    if payload.min_quantity is not None and payload.min_quantity != plan.min_quantity:
        changes["min_quantity"] = {"from": plan.min_quantity, "to": payload.min_quantity}
        plan.min_quantity = payload.min_quantity

    if payload.available_from is not None:
        plan.available_from = payload.available_from
    if payload.available_to is not None:
        plan.available_to = payload.available_to

    if payload.auto_close_on_expiry is not None:
        plan.auto_close_on_expiry = payload.auto_close_on_expiry
    if payload.allow_early_close is not None:
        plan.allow_early_close = payload.allow_early_close
    if payload.allow_pause is not None:
        plan.allow_pause = payload.allow_pause
    if payload.allow_renewal is not None:
        plan.allow_renewal = payload.allow_renewal

    if payload.is_active is not None and payload.is_active != plan.is_active:
        changes["is_active"] = {"from": plan.is_active, "to": payload.is_active}
        plan.is_active = payload.is_active

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

    plan_name = None
    plan_base_price = Decimal("0.00")

    # 1. Plan line (if selected)
    if payload.plan_id:
        plan_obj = (await db.execute(select(Plan).where(Plan.id == payload.plan_id))).scalar_one_or_none()
        if plan_obj:
            plan_name = plan_obj.name
            plan_base_price = _money(Decimal(str(plan_obj.base_price)))
            if not plan_obj.is_active:
                warnings.append("The selected plan is currently archived/inactive.")
            if plan_obj.available_from and as_of < plan_obj.available_from:
                warnings.append(f"Plan is not yet available (starts {plan_obj.available_from}).")
            if plan_obj.available_to and as_of > plan_obj.available_to:
                warnings.append(f"Plan availability expired on {plan_obj.available_to}.")

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

    # 2. Product lines with variant price adjustments
    total_qty = 0
    for req_line in payload.product_lines:
        prod = (await db.execute(select(Product).where(Product.id == req_line.product_id))).scalar_one_or_none()
        if not prod:
            continue

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
            if variant:
                adjustment = Decimal(str(variant.price_adjustment))
                variant_name = variant.name

        unit_price = _money(base_unit + adjustment)
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

    gross_subtotal = sum((l.subtotal for l in lines_output), Decimal("0.00"))

    # 3. Discount evaluation
    discount_amount = Decimal("0.00")
    discount_name = None

    if payload.discount_rule_id:
        disc = (
            await db.execute(select(DiscountRule).where(DiscountRule.id == payload.discount_rule_id))
        ).scalar_one_or_none()

        if disc:
            discount_name = disc.name
            if not disc.is_active:
                warnings.append(f"Discount '{disc.name}' is currently inactive.")
            elif not (disc.valid_from <= as_of <= disc.valid_to):
                warnings.append(f"Discount '{disc.name}' is outside its active validity window ({disc.valid_from} to {disc.valid_to}).")
            else:
                # Check redemptions count
                redemptions_query = select(func.count(DiscountRedemption.id)).where(
                    DiscountRedemption.discount_rule_id == disc.id
                )
                used_count = (await db.execute(redemptions_query)).scalar_one()

                if disc.max_usage_limit is not None and used_count >= disc.max_usage_limit:
                    warnings.append(f"Discount '{disc.name}' has reached its maximum usage cap ({disc.max_usage_limit}).")
                else:
                    # Scope check
                    eligible_subtotal = Decimal("0.00")
                    eligible_qty = 0

                    if disc.scope == DiscountScope.SUBSCRIPTION:
                        eligible_subtotal = gross_subtotal
                        eligible_qty = total_qty
                    elif disc.scope == DiscountScope.PRODUCT and disc.target_product_id:
                        for idx, pline in enumerate(payload.product_lines):
                            if pline.product_id == disc.target_product_id:
                                # Match corresponding line output
                                matching_out = [
                                    l for l in lines_output
                                    if l.product_name == prod.name or l.description.startswith(prod.name)
                                ]
                                for m in matching_out:
                                    eligible_subtotal += m.subtotal
                                    eligible_qty += m.quantity

                    if eligible_subtotal < disc.min_spend:
                        warnings.append(f"Subtotal ${eligible_subtotal} is below discount min spend ${disc.min_spend}.")
                    elif eligible_qty < disc.min_quantity:
                        warnings.append(f"Quantity {eligible_qty} is below discount min quantity {disc.min_quantity}.")
                    else:
                        if disc.discount_type == DiscountType.PERCENTAGE:
                            discount_amount = _money(eligible_subtotal * Decimal(str(disc.value)) / Decimal("100"))
                        else:
                            discount_amount = min(eligible_subtotal, Decimal(str(disc.value)))

    # Allocate discount proportionally across lines
    if gross_subtotal > Decimal("0.00") and discount_amount > Decimal("0.00"):
        allocated = Decimal("0.00")
        for i, l in enumerate(lines_output):
            if i == len(lines_output) - 1:
                l.discount_amount = discount_amount - allocated
            else:
                l_disc = _money(discount_amount * (l.subtotal / gross_subtotal))
                l.discount_amount = l_disc
                allocated += l_disc

    # 4. Tax evaluation
    tax_rules_cache = {}
    tax_amount = Decimal("0.00")

    for i, l in enumerate(lines_output):
        req_tax_id = None
        # Look up line tax id
        if i == 0 and payload.plan_id:
            req_tax_id = payload.default_tax_rule_id
        elif payload.product_lines:
            idx = i - 1 if payload.plan_id else i
            if 0 <= idx < len(payload.product_lines):
                req_tax_id = payload.product_lines[idx].tax_rule_id or payload.default_tax_rule_id

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

        l.line_total = _money(l.subtotal - l.discount_amount + l.tax_amount)

    total_amount = _money(gross_subtotal - discount_amount + tax_amount)

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
