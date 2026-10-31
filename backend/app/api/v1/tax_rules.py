import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tax import TaxRule
from app.models.user import User
from app.schemas.tax import TaxRuleCreate, TaxRuleUpdate, TaxRuleResponse
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get(
    "",
    response_model=Union[PaginatedResponse[TaxRuleResponse], List[TaxRuleResponse]],
    tags=["Tax Rules"],
)
async def list_tax_rules(
    response: Response,
    db: AsyncSession = Depends(get_db),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    search: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    envelope: bool = Query(False),
):
    """List configured tax rules with search and optional pagination."""
    query = select(TaxRule)
    count_query = select(func.count(TaxRule.id))

    if not include_inactive:
        query = query.where(TaxRule.is_active == True)  # noqa: E712
        count_query = count_query.where(TaxRule.is_active == True)  # noqa: E712

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(TaxRule.name.ilike(term))
        count_query = count_query.where(TaxRule.name.ilike(term))

    query = query.order_by(TaxRule.rate_percentage.asc())
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
    tax_rules = result.scalars().all()
    items = [TaxRuleResponse.model_validate(tr) for tr in tax_rules]

    if envelope:
        return PaginatedResponse[TaxRuleResponse](
            items=items,
            total=total_count,
            page=p,
            page_size=ps,
            total_pages=total_pages,
        )

    return items


@router.get("/{tax_rule_id}", response_model=TaxRuleResponse, tags=["Tax Rules"])
async def get_tax_rule(tax_rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Retrieve details for a single tax rule."""
    query = select(TaxRule).where(TaxRule.id == tax_rule_id)
    tax_rule = (await db.execute(query)).scalar_one_or_none()
    if not tax_rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax rule not found.")
    return TaxRuleResponse.model_validate(tax_rule)


@router.post(
    "",
    response_model=TaxRuleResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tax Rules"],
)
async def create_tax_rule(
    payload: TaxRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Create a new tax rule (e.g. GST 18%, VAT 20%). Admin only."""
    # Check for name uniqueness
    existing = (
        await db.execute(select(TaxRule).where(TaxRule.name.ilike(payload.name.strip())))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tax rule with name '{payload.name}' already exists.",
        )

    tax_rule = TaxRule(
        name=payload.name.strip(),
        rate_percentage=payload.rate_percentage,
        is_active=payload.is_active,
    )
    db.add(tax_rule)
    await db.flush()

    await record_audit_event(
        db,
        entity_type="tax_rule",
        entity_id=tax_rule.id,
        action="CREATE_TAX_RULE",
        actor_user_id=current_admin.id,
        changes={
            "name": tax_rule.name,
            "rate_percentage": str(tax_rule.rate_percentage),
        },
    )

    await db.commit()
    await db.refresh(tax_rule)
    return TaxRuleResponse.model_validate(tax_rule)


@router.put("/{tax_rule_id}", response_model=TaxRuleResponse, tags=["Tax Rules"])
@router.patch("/{tax_rule_id}", response_model=TaxRuleResponse, tags=["Tax Rules"])
async def update_tax_rule(
    tax_rule_id: uuid.UUID,
    payload: TaxRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update a tax rule. Admin only."""
    query = select(TaxRule).where(TaxRule.id == tax_rule_id)
    tax_rule = (await db.execute(query)).scalar_one_or_none()
    if not tax_rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax rule not found.")

    changes = {}
    if payload.name is not None and payload.name.strip() != tax_rule.name:
        changes["name"] = {"from": tax_rule.name, "to": payload.name.strip()}
        tax_rule.name = payload.name.strip()

    if payload.rate_percentage is not None and payload.rate_percentage != tax_rule.rate_percentage:
        changes["rate_percentage"] = {"from": str(tax_rule.rate_percentage), "to": str(payload.rate_percentage)}
        tax_rule.rate_percentage = payload.rate_percentage

    if payload.is_active is not None and payload.is_active != tax_rule.is_active:
        changes["is_active"] = {"from": tax_rule.is_active, "to": payload.is_active}
        tax_rule.is_active = payload.is_active

    if changes:
        await record_audit_event(
            db,
            entity_type="tax_rule",
            entity_id=tax_rule.id,
            action="UPDATE_TAX_RULE",
            actor_user_id=current_admin.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(tax_rule)

    return TaxRuleResponse.model_validate(tax_rule)


@router.delete("/{tax_rule_id}", tags=["Tax Rules"])
async def archive_tax_rule(
    tax_rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Archive a tax rule so it is not applied to future calculations. Admin only."""
    query = select(TaxRule).where(TaxRule.id == tax_rule_id)
    tax_rule = (await db.execute(query)).scalar_one_or_none()
    if not tax_rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax rule not found.")

    tax_rule.is_active = False
    await record_audit_event(
        db,
        entity_type="tax_rule",
        entity_id=tax_rule.id,
        action="ARCHIVE_TAX_RULE",
        actor_user_id=current_admin.id,
        changes={"is_active": False},
    )
    await db.commit()
    return {"message": f"Tax rule '{tax_rule.name}' archived successfully.", "is_active": False}
