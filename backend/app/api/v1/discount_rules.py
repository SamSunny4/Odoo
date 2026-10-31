import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.discount import DiscountRule, DiscountRedemption, DiscountScope, DiscountType
from app.models.catalog import Product
from app.models.user import User
from app.schemas.discount import DiscountRuleCreate, DiscountRuleUpdate, DiscountRuleResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get(
    "",
    response_model=Union[PaginatedResponse[DiscountRuleResponse], List[DiscountRuleResponse]],
    tags=["Discount Rules"],
)
async def list_discount_rules(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    envelope: bool = Query(False),
):
    """
    List discount rules with usage statistics.
    Strictly restricted to Administrator role.
    """
    query = select(DiscountRule)
    count_query = select(func.count(DiscountRule.id))

    if not include_inactive:
        query = query.where(DiscountRule.is_active == True)  # noqa: E712
        count_query = count_query.where(DiscountRule.is_active == True)  # noqa: E712

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(DiscountRule.name.ilike(term))
        count_query = count_query.where(DiscountRule.name.ilike(term))

    query = query.order_by(DiscountRule.created_at.desc())
    total_count = (await db.execute(count_query)).scalar_one()

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
    rules = result.scalars().all()

    items = []
    for r in rules:
        # Count actual redemptions
        used_count = (
            await db.execute(
                select(func.count(DiscountRedemption.id)).where(
                    DiscountRedemption.discount_rule_id == r.id
                )
            )
        ).scalar_one()

        prod_name = None
        if r.target_product_id:
            target_prod = (
                await db.execute(select(Product).where(Product.id == r.target_product_id))
            ).scalar_one_or_none()
            if target_prod:
                prod_name = target_prod.name

        resp_dict = DiscountRuleResponse(
            id=r.id,
            name=r.name,
            discount_type=r.discount_type,
            value=r.value,
            scope=r.scope,
            target_product_id=r.target_product_id,
            target_product_name=prod_name,
            min_spend=r.min_spend,
            min_quantity=r.min_quantity,
            max_usage_limit=r.max_usage_limit,
            current_usage_count=used_count,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
            is_active=r.is_active,
            created_at=r.created_at,
        )
        items.append(resp_dict)

    if envelope:
        return PaginatedResponse[DiscountRuleResponse](
            items=items,
            total=total_count,
            page=p,
            page_size=ps,
            total_pages=total_pages,
        )

    return items


@router.get("/{discount_rule_id}", response_model=DiscountRuleResponse, tags=["Discount Rules"])
async def get_discount_rule(
    discount_rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Retrieve details for a single discount rule. Admin only."""
    query = select(DiscountRule).where(DiscountRule.id == discount_rule_id)
    r = (await db.execute(query)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found.")

    used_count = (
        await db.execute(
            select(func.count(DiscountRedemption.id)).where(
                DiscountRedemption.discount_rule_id == r.id
            )
        )
    ).scalar_one()

    prod_name = None
    if r.target_product_id:
        target_prod = (
            await db.execute(select(Product).where(Product.id == r.target_product_id))
        ).scalar_one_or_none()
        if target_prod:
            prod_name = target_prod.name

    return DiscountRuleResponse(
        id=r.id,
        name=r.name,
        discount_type=r.discount_type,
        value=r.value,
        scope=r.scope,
        target_product_id=r.target_product_id,
        target_product_name=prod_name,
        min_spend=r.min_spend,
        min_quantity=r.min_quantity,
        max_usage_limit=r.max_usage_limit,
        current_usage_count=used_count,
        valid_from=r.valid_from,
        valid_to=r.valid_to,
        is_active=r.is_active,
        created_at=r.created_at,
    )


@router.post(
    "",
    response_model=DiscountRuleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Discount Rules"],
)
async def create_discount_rule(
    payload: DiscountRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """
    Create a new discount rule with thresholds and usage caps.
    Strictly restricted to Administrator role.
    """
    if payload.scope == DiscountScope.PRODUCT and payload.target_product_id:
        prod = (
            await db.execute(select(Product).where(Product.id == payload.target_product_id))
        ).scalar_one_or_none()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target product {payload.target_product_id} not found.",
            )

    rule = DiscountRule(
        name=payload.name.strip(),
        discount_type=payload.discount_type,
        value=payload.value,
        scope=payload.scope,
        target_product_id=payload.target_product_id,
        min_spend=payload.min_spend,
        min_quantity=payload.min_quantity,
        max_usage_limit=payload.max_usage_limit,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        is_active=payload.is_active,
    )
    db.add(rule)
    await db.flush()

    await record_audit_event(
        db,
        entity_type="discount_rule",
        entity_id=rule.id,
        action="CREATE_DISCOUNT_RULE",
        actor_user_id=current_admin.id,
        changes={
            "name": rule.name,
            "discount_type": rule.discount_type.value,
            "value": str(rule.value),
            "scope": rule.scope.value,
            "max_usage_limit": rule.max_usage_limit,
        },
    )

    await db.commit()
    await db.refresh(rule)

    prod_name = None
    if rule.target_product_id:
        target_prod = (
            await db.execute(select(Product).where(Product.id == rule.target_product_id))
        ).scalar_one_or_none()
        if target_prod:
            prod_name = target_prod.name

    return DiscountRuleResponse(
        id=rule.id,
        name=rule.name,
        discount_type=rule.discount_type,
        value=rule.value,
        scope=rule.scope,
        target_product_id=rule.target_product_id,
        target_product_name=prod_name,
        min_spend=rule.min_spend,
        min_quantity=rule.min_quantity,
        max_usage_limit=rule.max_usage_limit,
        current_usage_count=0,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


@router.put("/{discount_rule_id}", response_model=DiscountRuleResponse, tags=["Discount Rules"])
@router.patch("/{discount_rule_id}", response_model=DiscountRuleResponse, tags=["Discount Rules"])
async def update_discount_rule(
    discount_rule_id: uuid.UUID,
    payload: DiscountRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update a discount rule. Admin only."""
    query = select(DiscountRule).where(DiscountRule.id == discount_rule_id)
    rule = (await db.execute(query)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found.")

    changes = {}
    if payload.name is not None and payload.name.strip() != rule.name:
        changes["name"] = {"from": rule.name, "to": payload.name.strip()}
        rule.name = payload.name.strip()

    if payload.discount_type is not None and payload.discount_type != rule.discount_type:
        changes["discount_type"] = {"from": rule.discount_type.value, "to": payload.discount_type.value}
        rule.discount_type = payload.discount_type

    if payload.value is not None and payload.value != rule.value:
        changes["value"] = {"from": str(rule.value), "to": str(payload.value)}
        rule.value = payload.value

    if payload.scope is not None and payload.scope != rule.scope:
        changes["scope"] = {"from": rule.scope.value, "to": payload.scope.value}
        rule.scope = payload.scope

    if payload.target_product_id is not None:
        rule.target_product_id = payload.target_product_id

    if payload.min_spend is not None:
        rule.min_spend = payload.min_spend
    if payload.min_quantity is not None:
        rule.min_quantity = payload.min_quantity
    if payload.max_usage_limit is not None:
        rule.max_usage_limit = payload.max_usage_limit
    if payload.valid_from is not None:
        rule.valid_from = payload.valid_from
    if payload.valid_to is not None:
        rule.valid_to = payload.valid_to
    if payload.is_active is not None and payload.is_active != rule.is_active:
        changes["is_active"] = {"from": rule.is_active, "to": payload.is_active}
        rule.is_active = payload.is_active

    if changes:
        await record_audit_event(
            db,
            entity_type="discount_rule",
            entity_id=rule.id,
            action="UPDATE_DISCOUNT_RULE",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(rule)

    used_count = (
        await db.execute(
            select(func.count(DiscountRedemption.id)).where(
                DiscountRedemption.discount_rule_id == rule.id
            )
        )
    ).scalar_one()

    prod_name = None
    if rule.target_product_id:
        target_prod = (
            await db.execute(select(Product).where(Product.id == rule.target_product_id))
        ).scalar_one_or_none()
        if target_prod:
            prod_name = target_prod.name

    return DiscountRuleResponse(
        id=rule.id,
        name=rule.name,
        discount_type=rule.discount_type,
        value=rule.value,
        scope=rule.scope,
        target_product_id=rule.target_product_id,
        target_product_name=prod_name,
        min_spend=rule.min_spend,
        min_quantity=rule.min_quantity,
        max_usage_limit=rule.max_usage_limit,
        current_usage_count=used_count,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


@router.delete("/{discount_rule_id}", tags=["Discount Rules"])
async def archive_discount_rule(
    discount_rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Archive a discount rule so it is not eligible for new invoices. Admin only."""
    query = select(DiscountRule).where(DiscountRule.id == discount_rule_id)
    rule = (await db.execute(query)).scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount rule not found.")

    rule.is_active = False
    await record_audit_event(
        db,
        entity_type="discount_rule",
        entity_id=rule.id,
        action="ARCHIVE_DISCOUNT_RULE",
        actor_user_id=current_admin.id,
        changes={"is_active": False},
    )
    await db.commit()
    return {"message": f"Discount rule '{rule.name}' archived successfully.", "is_active": False}
