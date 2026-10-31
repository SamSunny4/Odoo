import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.quote_template import QuotationTemplate
from app.models.plan import Plan
from app.models.catalog import Product, ProductVariant
from app.models.user import User
from app.schemas.quote_template import (
    QuotationTemplateCreate,
    QuotationTemplateUpdate,
    QuotationTemplateResponse,
)
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get(
    "",
    response_model=Union[PaginatedResponse[QuotationTemplateResponse], List[QuotationTemplateResponse]],
    tags=["Quotation Templates"],
)
async def list_quotation_templates(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
    page: Optional[int] = Query(None, ge=1),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    search: Optional[str] = Query(None),
    envelope: bool = Query(False),
):
    """List quotation templates with search and optional pagination."""
    query = select(QuotationTemplate)
    count_query = select(func.count(QuotationTemplate.id))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(QuotationTemplate.name.ilike(term))
        count_query = count_query.where(QuotationTemplate.name.ilike(term))

    query = query.order_by(QuotationTemplate.created_at.desc())

    if page is not None and page_size is not None:
        total_count = (await db.execute(count_query)).scalar_one()
        query = query.offset((page - 1) * page_size).limit(page_size)
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Page"] = str(page)
        response.headers["X-Page-Size"] = str(page_size)
        response.headers["X-Total-Pages"] = str(total_pages)
    else:
        total_count = 0
        total_pages = 1

    templates = (await db.execute(query)).scalars().all()

    # Enrich with default plan name
    plan_ids = [t.default_plan_id for t in templates if t.default_plan_id]
    plans_map = {}
    if plan_ids:
        plan_rows = (await db.execute(select(Plan).where(Plan.id.in_(plan_ids)))).scalars().all()
        plans_map = {p.id: p.name for p in plan_rows}

    items = []
    for t in templates:
        resp = QuotationTemplateResponse.model_validate(t)
        resp.default_plan_name = plans_map.get(t.default_plan_id) if t.default_plan_id else None
        items.append(resp)

    if envelope:
        return PaginatedResponse[QuotationTemplateResponse](
            items=items,
            total=total_count if total_count > 0 else len(items),
            page=page or 1,
            page_size=page_size or len(items),
            total_pages=total_pages,
        )

    return items


@router.post(
    "",
    response_model=QuotationTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Quotation Templates"],
)
async def create_quotation_template(
    payload: QuotationTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Create a new reusable quotation template. Staff or Admin role."""
    plan_name = None
    if payload.default_plan_id:
        plan = (await db.execute(select(Plan).where(Plan.id == payload.default_plan_id))).scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {payload.default_plan_id} not found.",
            )
        if not plan.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Plan '{plan.name}' is archived and cannot be used in a new template.")
        plan_name = plan.name

    # Validate line products if provided
    raw_lines = []
    for line in payload.default_lines:
        prod = (await db.execute(select(Product).where(Product.id == line.product_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {line.product_id} not found.",
            )
        if not prod.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product '{prod.name}' is archived and cannot be added to a new template.")
        var_name = None
        if line.product_variant_id:
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == line.product_variant_id,
                        ProductVariant.product_id == prod.id,
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product variant {line.product_variant_id} not found for product {prod.name}.",
                )
            if not variant.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variant '{variant.name}' is archived and cannot be added to a new template.")
            var_name = variant.name

        raw_lines.append(
            {
                "product_id": str(line.product_id),
                "product_name": prod.name,
                "product_variant_id": str(line.product_variant_id) if line.product_variant_id else None,
                "variant_name": var_name,
                "quantity": line.quantity,
            }
        )

    template = QuotationTemplate(
        name=payload.name.strip(),
        validity_days=payload.validity_days,
        default_plan_id=payload.default_plan_id,
        default_lines=raw_lines,
    )
    db.add(template)
    await db.flush()

    await record_audit_event(
        db,
        entity_type="quotation_template",
        entity_id=template.id,
        action="CREATE_TEMPLATE",
        actor_user_id=current_user.id,
        changes={"name": template.name, "validity_days": template.validity_days},
    )

    await db.commit()
    await db.refresh(template)

    resp = QuotationTemplateResponse.model_validate(template)
    resp.default_plan_name = plan_name
    return resp


@router.get(
    "/{template_id}",
    response_model=QuotationTemplateResponse,
    tags=["Quotation Templates"],
)
async def get_quotation_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """Retrieve template details with enriched line product and variant info."""
    template = (
        await db.execute(select(QuotationTemplate).where(QuotationTemplate.id == template_id))
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation template not found.",
        )

    plan_name = None
    if template.default_plan_id:
        plan = (await db.execute(select(Plan).where(Plan.id == template.default_plan_id))).scalar_one_or_none()
        if plan:
            plan_name = plan.name

    resp = QuotationTemplateResponse.model_validate(template)
    resp.default_plan_name = plan_name
    return resp


@router.put(
    "/{template_id}",
    response_model=QuotationTemplateResponse,
    tags=["Quotation Templates"],
)
@router.patch(
    "/{template_id}",
    response_model=QuotationTemplateResponse,
    tags=["Quotation Templates"],
)
async def update_quotation_template(
    template_id: uuid.UUID,
    payload: QuotationTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Update quotation template attributes or default lines."""
    template = (
        await db.execute(select(QuotationTemplate).where(QuotationTemplate.id == template_id))
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation template not found.",
        )

    changes = {}
    if payload.name is not None and payload.name.strip() != template.name:
        changes["name"] = {"from": template.name, "to": payload.name.strip()}
        template.name = payload.name.strip()

    if payload.validity_days is not None and payload.validity_days != template.validity_days:
        changes["validity_days"] = {"from": template.validity_days, "to": payload.validity_days}
        template.validity_days = payload.validity_days

    if payload.default_plan_id is not None and payload.default_plan_id != template.default_plan_id:
        plan = (await db.execute(select(Plan).where(Plan.id == payload.default_plan_id))).scalar_one_or_none()
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan {payload.default_plan_id} not found.",
            )
        if not plan.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Plan '{plan.name}' is archived and cannot be used in a new template.")
        changes["default_plan_id"] = {"from": str(template.default_plan_id), "to": str(payload.default_plan_id)}
        template.default_plan_id = payload.default_plan_id

    if payload.default_lines is not None:
        raw_lines = []
        for line in payload.default_lines:
            prod = (await db.execute(select(Product).where(Product.id == line.product_id))).scalar_one_or_none()
            if not prod:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {line.product_id} not found.",
                )
            if not prod.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Product '{prod.name}' is archived and cannot be added to a new template.")
            var_name = None
            if line.product_variant_id:
                variant = (
                    await db.execute(
                        select(ProductVariant).where(
                            ProductVariant.id == line.product_variant_id,
                            ProductVariant.product_id == prod.id,
                        )
                    )
                ).scalar_one_or_none()
                if not variant:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Product variant {line.product_variant_id} not found for product {prod.name}.",
                    )
                if not variant.is_active:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Variant '{variant.name}' is archived and cannot be added to a new template.")
                var_name = variant.name

            raw_lines.append(
                {
                    "product_id": str(line.product_id),
                    "product_name": prod.name,
                    "product_variant_id": str(line.product_variant_id) if line.product_variant_id else None,
                    "variant_name": var_name,
                    "quantity": line.quantity,
                }
            )
        changes["default_lines"] = {"from": len(template.default_lines), "to": len(raw_lines)}
        template.default_lines = raw_lines

    if changes:
        await record_audit_event(
            db,
            entity_type="quotation_template",
            entity_id=template.id,
            action="UPDATE_TEMPLATE",
            actor_user_id=current_user.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(template)

    plan_name = None
    if template.default_plan_id:
        plan = (await db.execute(select(Plan).where(Plan.id == template.default_plan_id))).scalar_one_or_none()
        if plan:
            plan_name = plan.name

    resp = QuotationTemplateResponse.model_validate(template)
    resp.default_plan_name = plan_name
    return resp


@router.delete(
    "/{template_id}",
    tags=["Quotation Templates"],
)
async def delete_quotation_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """Delete a quotation template."""
    template = (
        await db.execute(select(QuotationTemplate).where(QuotationTemplate.id == template_id))
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quotation template not found.",
        )

    await record_audit_event(
        db,
        entity_type="quotation_template",
        entity_id=template.id,
        action="DELETE_TEMPLATE",
        actor_user_id=current_user.id,
        changes={"name": template.name},
    )
    await db.delete(template)
    await db.commit()

    return {"message": f"Template '{template.name}' deleted successfully."}

