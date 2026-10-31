import uuid
from datetime import date, timedelta
from typing import List, Optional, Union
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.customer import CustomerAccount
from app.models.plan import Plan, BillingCadence
from app.models.catalog import Product, ProductVariant
from app.models.tax import TaxRule
from app.models.quote_template import QuotationTemplate
from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.subscription import (
    SubscriptionResponse,
    SubscriptionDetailResponse,
    SubscriptionLineResponse,
    SubscriptionCreate,
    SubscriptionUpdate,
    SubscriptionStatusAction,
    SubscriptionAuditItem,
)
from app.schemas.pagination import PaginatedResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event
from app.services.billing import compute_next_billing_date

CENT = Decimal("0.01")


def _money(val: Decimal) -> Decimal:
    return val.quantize(CENT, rounding=ROUND_HALF_UP)


router = APIRouter()


async def generate_subscription_number(db: AsyncSession) -> str:
    """Generate sequential unique subscription number like SUB-2026-0001."""
    year = date.today().year
    count_query = select(func.count(Subscription.id))
    total_count = (await db.execute(count_query)).scalar_one()
    seq = total_count + 1
    while True:
        candidate = f"SUB-{year}-{seq:04d}"
        exists = (
            await db.execute(select(Subscription.id).where(Subscription.subscription_number == candidate))
        ).scalar_one_or_none()
        if not exists:
            return candidate
        seq += 1


def _subscription_query_options():
    return [
        selectinload(Subscription.customer_account),
        selectinload(Subscription.plan),
        selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
        selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        selectinload(Subscription.lines).selectinload(SubscriptionLine.tax_rule),
    ]


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
    status: Optional[str] = Query(None, description="Filter by status: active, quotation, paused, closed, draft, confirmed"),
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
        .options(*_subscription_query_options())
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
                    product_variant_id=line.product_variant_id,
                    variant_name=line.variant.name if line.variant else None,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rule_id=line.tax_rule_id,
                    tax_rate=Decimal(str(line.tax_rule.rate_percentage)) if line.tax_rule else None,
                    line_subtotal=_money(line_price),
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
                total_amount=_money(total),
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


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Subscriptions"],
)
async def create_subscription(
    payload: SubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Create a new draft subscription or quotation with unique number, customer, plan, lines, and payment terms.
    Can be instantiated from an optional quotation template.
    """
    # 1. Validate Customer Account
    customer = (
        await db.execute(select(CustomerAccount).where(CustomerAccount.id == payload.customer_account_id))
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer account {payload.customer_account_id} not found.",
        )

    # 2. Validate Plan
    plan = (await db.execute(select(Plan).where(Plan.id == payload.plan_id))).scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan {payload.plan_id} not found.",
        )
    if not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plan '{plan.name}' is archived and cannot be chosen for new agreements.",
        )

    # 3. Check Quotation Template defaults if supplied
    lines_to_add = list(payload.lines)
    expiry = payload.expiry_date

    if payload.template_id:
        template = (
            await db.execute(select(QuotationTemplate).where(QuotationTemplate.id == payload.template_id))
        ).scalar_one_or_none()
        if template:
            if not expiry and template.validity_days:
                base_start = payload.start_date or date.today()
                expiry = base_start + timedelta(days=template.validity_days)
            if not lines_to_add and template.default_lines:
                for dl in template.default_lines:
                    lines_to_add.append(
                        {
                            "product_id": uuid.UUID(dl["product_id"]),
                            "product_variant_id": uuid.UUID(dl["product_variant_id"]) if dl.get("product_variant_id") else None,
                            "quantity": dl.get("quantity", 1),
                            "unit_price": None,
                            "tax_rule_id": None,
                        }
                    )

    start = payload.start_date or date.today()
    anchor_day = payload.billing_anchor_day or start.day
    anchor_day = max(1, min(31, anchor_day))

    # Next billing date initialization: if starting as active, due on start_date
    next_bill = start if payload.status == SubscriptionStatus.ACTIVE else None

    # 4. Generate unique subscription number
    sub_num = await generate_subscription_number(db)

    sub = Subscription(
        subscription_number=sub_num,
        customer_account_id=customer.id,
        plan_id=plan.id,
        status=payload.status,
        start_date=start,
        expiry_date=expiry,
        next_billing_date=next_bill,
        billing_anchor_day=anchor_day,
        payment_terms_days=payload.payment_terms_days,
    )
    db.add(sub)
    await db.flush()

    # 5. Populate Lines
    created_lines = []
    total_amount = Decimal(str(plan.base_price))

    for line_data in lines_to_add:
        p_id = line_data.product_id if hasattr(line_data, "product_id") else line_data["product_id"]
        v_id = line_data.product_variant_id if hasattr(line_data, "product_variant_id") else line_data.get("product_variant_id")
        qty = line_data.quantity if hasattr(line_data, "quantity") else line_data.get("quantity", 1)
        req_price = line_data.unit_price if hasattr(line_data, "unit_price") else line_data.get("unit_price")
        t_id = line_data.tax_rule_id if hasattr(line_data, "tax_rule_id") else line_data.get("tax_rule_id")

        prod = (await db.execute(select(Product).where(Product.id == p_id))).scalar_one_or_none()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {p_id} not found.",
            )

        var = None
        var_adjustment = Decimal("0.00")
        if v_id:
            var = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == v_id,
                        ProductVariant.product_id == prod.id,
                    )
                )
            ).scalar_one_or_none()
            if not var:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant {v_id} not found for product {prod.name}.",
                )
            var_adjustment = Decimal(str(var.price_adjustment))

        if req_price is not None:
            unit_price = _money(Decimal(str(req_price)))
        else:
            unit_price = _money(Decimal(str(prod.sales_price)) + var_adjustment)

        sub_line = SubscriptionLine(
            subscription_id=sub.id,
            product_id=prod.id,
            product_variant_id=var.id if var else None,
            quantity=qty,
            unit_price=unit_price,
            tax_rule_id=t_id,
        )
        db.add(sub_line)
        await db.flush()
        created_lines.append(sub_line)
        total_amount += _money(unit_price * qty)

    # 6. Audit event
    action_name = "CREATE_QUOTATION" if sub.status == SubscriptionStatus.QUOTATION else "CREATE_SUBSCRIPTION"
    await record_audit_event(
        db,
        entity_type="subscription",
        entity_id=sub.id,
        action=action_name,
        actor_user_id=current_user.id,
        changes={
            "subscription_number": sub.subscription_number,
            "customer_id": str(customer.id),
            "customer_name": customer.company_name,
            "plan_name": plan.name,
            "status": sub.status.value,
            "line_count": len(created_lines),
            "total_amount": str(total_amount),
        },
    )

    await db.commit()
    await db.refresh(sub, ["customer_account", "plan", "lines"])

    line_responses = []
    for l in sub.lines:
        line_price = Decimal(str(l.unit_price)) * l.quantity
        line_responses.append(
            SubscriptionLineResponse(
                id=l.id,
                product_id=l.product_id,
                product_name=l.product.name if l.product else "Product",
                product_variant_id=l.product_variant_id,
                variant_name=l.variant.name if l.variant else None,
                quantity=l.quantity,
                unit_price=l.unit_price,
                tax_rule_id=l.tax_rule_id,
                tax_rate=Decimal(str(l.tax_rule.rate_percentage)) if l.tax_rule else None,
                line_subtotal=_money(line_price),
            )
        )

    return SubscriptionResponse(
        id=sub.id,
        subscription_number=sub.subscription_number,
        customer_account_id=sub.customer_account_id,
        customer_name=customer.company_name,
        plan_id=sub.plan_id,
        plan_name=plan.name,
        status=sub.status,
        start_date=sub.start_date,
        expiry_date=sub.expiry_date,
        next_billing_date=sub.next_billing_date,
        billing_anchor_day=sub.billing_anchor_day,
        payment_terms_days=sub.payment_terms_days,
        total_amount=_money(total_amount),
        lines=line_responses,
    )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionDetailResponse,
    tags=["Subscriptions"],
)
async def get_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """
    Retrieve full subscription details including customer info, plan policies,
    lines, taxes, and traceable audit history.
    """
    query = (
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(*_subscription_query_options())
    )
    sub = (await db.execute(query)).scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )

    # Compute lines & totals
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
                product_variant_id=line.product_variant_id,
                variant_name=line.variant.name if line.variant else None,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rule_id=line.tax_rule_id,
                tax_rate=Decimal(str(line.tax_rule.rate_percentage)) if line.tax_rule else None,
                line_subtotal=_money(line_price),
            )
        )

    # Traceable audit events
    audit_query = (
        select(AuditEvent, User)
        .outerjoin(User, AuditEvent.actor_user_id == User.id)
        .where(
            AuditEvent.entity_type == "subscription",
            AuditEvent.entity_id == sub.id,
        )
        .order_by(AuditEvent.timestamp.desc())
    )
    audit_rows = (await db.execute(audit_query)).all()

    audit_items = []
    for event, actor in audit_rows:
        audit_items.append(
            SubscriptionAuditItem(
                id=event.id,
                action=event.action,
                changes=event.changes_json or {},
                actor_user_id=event.actor_user_id,
                actor_name=actor.full_name if actor else "System",
                actor_email=actor.email if actor else None,
                actor_role=actor.role.value if actor else None,
                timestamp=event.timestamp,
            )
        )

    return SubscriptionDetailResponse(
        id=sub.id,
        subscription_number=sub.subscription_number,
        customer_account_id=sub.customer_account_id,
        customer_name=sub.customer_account.company_name if sub.customer_account else "Unknown",
        customer_billing_email=sub.customer_account.billing_email if sub.customer_account else None,
        customer_address=sub.customer_account.billing_address_line1 if sub.customer_account else None,
        plan_id=sub.plan_id,
        plan_name=sub.plan.name if sub.plan else "Unknown",
        plan_cadence=sub.plan.cadence.value if sub.plan else None,
        plan_base_price=Decimal(str(sub.plan.base_price)) if sub.plan else Decimal("0.00"),
        plan_allow_pause=sub.plan.allow_pause if sub.plan else True,
        plan_allow_early_close=sub.plan.allow_early_close if sub.plan else True,
        plan_allow_renewal=sub.plan.allow_renewal if sub.plan else True,
        plan_auto_close_on_expiry=sub.plan.auto_close_on_expiry if sub.plan else False,
        status=sub.status,
        start_date=sub.start_date,
        expiry_date=sub.expiry_date,
        next_billing_date=sub.next_billing_date,
        billing_anchor_day=sub.billing_anchor_day,
        payment_terms_days=sub.payment_terms_days,
        total_amount=_money(total),
        lines=line_responses,
        audit_history=audit_items,
    )


@router.put(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
@router.patch(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def update_subscription(
    subscription_id: uuid.UUID,
    payload: SubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Update subscription terms or line items. Allowed for DRAFT or QUOTATION status.
    """
    query = (
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(*_subscription_query_options())
    )
    sub = (await db.execute(query)).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    if sub.status not in [SubscriptionStatus.DRAFT, SubscriptionStatus.QUOTATION]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subscription is currently '{sub.status.value}'. Only draft subscriptions or quotations can be modified.",
        )

    changes = {}
    if payload.plan_id is not None and payload.plan_id != sub.plan_id:
        new_plan = (await db.execute(select(Plan).where(Plan.id == payload.plan_id))).scalar_one_or_none()
        if not new_plan or not new_plan.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected plan is invalid or inactive.")
        changes["plan_id"] = {"from": str(sub.plan_id), "to": str(new_plan.id)}
        sub.plan_id = new_plan.id

    if payload.start_date is not None and payload.start_date != sub.start_date:
        changes["start_date"] = {"from": str(sub.start_date), "to": str(payload.start_date)}
        sub.start_date = payload.start_date

    if payload.expiry_date is not None and payload.expiry_date != sub.expiry_date:
        changes["expiry_date"] = {"from": str(sub.expiry_date), "to": str(payload.expiry_date)}
        sub.expiry_date = payload.expiry_date

    if payload.billing_anchor_day is not None and payload.billing_anchor_day != sub.billing_anchor_day:
        changes["billing_anchor_day"] = {"from": sub.billing_anchor_day, "to": payload.billing_anchor_day}
        sub.billing_anchor_day = payload.billing_anchor_day

    if payload.payment_terms_days is not None and payload.payment_terms_days != sub.payment_terms_days:
        changes["payment_terms_days"] = {"from": sub.payment_terms_days, "to": payload.payment_terms_days}
        sub.payment_terms_days = payload.payment_terms_days

    # Update line items if provided
    if payload.lines is not None:
        # Delete old lines
        for old_line in sub.lines:
            await db.delete(old_line)
        await db.flush()

        changes["lines_updated"] = len(payload.lines)

        for line_data in payload.lines:
            prod = (await db.execute(select(Product).where(Product.id == line_data.product_id))).scalar_one_or_none()
            if not prod:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {line_data.product_id} not found.")

            var = None
            var_adjustment = Decimal("0.00")
            if line_data.product_variant_id:
                var = (
                    await db.execute(
                        select(ProductVariant).where(
                            ProductVariant.id == line_data.product_variant_id,
                            ProductVariant.product_id == prod.id,
                        )
                    )
                ).scalar_one_or_none()
                if not var:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Variant {line_data.product_variant_id} not found for product {prod.name}.",
                    )
                var_adjustment = Decimal(str(var.price_adjustment))

            if line_data.unit_price is not None:
                unit_price = _money(Decimal(str(line_data.unit_price)))
            else:
                unit_price = _money(Decimal(str(prod.sales_price)) + var_adjustment)

            new_line = SubscriptionLine(
                subscription_id=sub.id,
                product_id=prod.id,
                product_variant_id=var.id if var else None,
                quantity=line_data.quantity,
                unit_price=unit_price,
                tax_rule_id=line_data.tax_rule_id,
            )
            db.add(new_line)

    if changes:
        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="UPDATE_SUBSCRIPTION",
            actor_user_id=current_user.id,
            changes=changes,
        )
        await db.commit()
        await db.refresh(sub, ["customer_account", "plan", "lines"])

    # Format response
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
                product_variant_id=line.product_variant_id,
                variant_name=line.variant.name if line.variant else None,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rule_id=line.tax_rule_id,
                tax_rate=Decimal(str(line.tax_rule.rate_percentage)) if line.tax_rule else None,
                line_subtotal=_money(line_price),
            )
        )

    return SubscriptionResponse(
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
        total_amount=_money(total),
        lines=line_responses,
    )


@router.post(
    "/{subscription_id}/status",
    response_model=SubscriptionResponse,
    tags=["Subscriptions"],
)
async def transition_subscription_status(
    subscription_id: uuid.UUID,
    payload: SubscriptionStatusAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff_or_admin),
):
    """
    Manage quotation and subscription state transitions with plan policy checks:
    - issue_quote: DRAFT -> QUOTATION
    - confirm: QUOTATION/DRAFT -> CONFIRMED (Customer accepted quote)
    - activate: CONFIRMED -> ACTIVE (Calculates initial next_billing_date)
    - pause: ACTIVE -> PAUSED (Checks plan.allow_pause)
    - resume: PAUSED -> ACTIVE
    - renew: ACTIVE -> ACTIVE (Checks plan.allow_renewal, extends expiry date)
    - close: ACTIVE/PAUSED/CONFIRMED/QUOTATION -> CLOSED (Checks plan.allow_early_close if before expiration)
    """
    query = (
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(*_subscription_query_options())
    )
    sub = (await db.execute(query)).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    action = payload.action.strip().lower()
    old_status = sub.status

    if action == "issue_quote":
        if sub.status != SubscriptionStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot issue quote: current status is '{sub.status.value}' (expected 'draft').",
            )
        sub.status = SubscriptionStatus.QUOTATION
        if not sub.expiry_date:
            sub.expiry_date = sub.start_date + timedelta(days=30)

        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="ISSUE_QUOTATION",
            actor_user_id=current_user.id,
            changes={"old_status": old_status.value, "new_status": sub.status.value, "reason": payload.reason},
        )

    elif action == "confirm":
        if sub.status not in [SubscriptionStatus.QUOTATION, SubscriptionStatus.DRAFT]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm: current status is '{sub.status.value}'.",
            )
        sub.status = SubscriptionStatus.CONFIRMED
        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="CONFIRM_QUOTATION",
            actor_user_id=current_user.id,
            changes={"old_status": old_status.value, "new_status": sub.status.value, "reason": payload.reason},
        )

    elif action == "activate":
        if sub.status != SubscriptionStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot activate: current status is '{sub.status.value}' (must be 'confirmed' first).",
            )
        if sub.plan and not sub.plan.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan '{sub.plan.name}' is archived. Update to an active plan before activation.",
            )
        sub.status = SubscriptionStatus.ACTIVE
        sub.next_billing_date = sub.start_date

        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="ACTIVATE_SUBSCRIPTION",
            actor_user_id=current_user.id,
            changes={
                "old_status": old_status.value,
                "new_status": sub.status.value,
                "next_billing_date": str(sub.next_billing_date),
            },
        )

    elif action == "pause":
        if sub.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only active subscriptions can be paused.",
            )
        if sub.plan and not sub.plan.allow_pause:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan policy for '{sub.plan.name}' does not permit pausing.",
            )
        sub.status = SubscriptionStatus.PAUSED
        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="PAUSE",
            actor_user_id=current_user.id,
            changes={"old_status": old_status.value, "new_status": sub.status.value, "reason": payload.reason},
        )

    elif action == "resume":
        if sub.status != SubscriptionStatus.PAUSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only paused subscriptions can be resumed.",
            )
        sub.status = SubscriptionStatus.ACTIVE
        if sub.next_billing_date and sub.next_billing_date < date.today():
            sub.next_billing_date = date.today()

        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="RESUME",
            actor_user_id=current_user.id,
            changes={
                "old_status": old_status.value,
                "new_status": sub.status.value,
                "next_billing_date": str(sub.next_billing_date) if sub.next_billing_date else None,
            },
        )

    elif action == "renew":
        if sub.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only active subscriptions can be renewed.",
            )
        if sub.plan and not sub.plan.allow_renewal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan policy for '{sub.plan.name}' does not permit renewal.",
            )
        if payload.renewal_duration_days:
            extension_days = payload.renewal_duration_days
        else:
            cadence = sub.plan.cadence if sub.plan else BillingCadence.MONTHLY
            if cadence == BillingCadence.YEARLY:
                extension_days = 365
            elif cadence == BillingCadence.WEEKLY:
                extension_days = 7
            elif cadence == BillingCadence.DAILY:
                extension_days = 1
            else:
                extension_days = 30

        current_end = sub.expiry_date or date.today()
        new_end = current_end + timedelta(days=extension_days)
        old_end_str = str(sub.expiry_date) if sub.expiry_date else None
        sub.expiry_date = new_end

        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="RENEW",
            actor_user_id=current_user.id,
            changes={
                "old_expiry_date": old_end_str,
                "new_expiry_date": str(new_end),
                "extension_days": extension_days,
            },
        )

    elif action in ["close", "early_close", "cancel"]:
        if sub.status == SubscriptionStatus.CLOSED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is already closed.",
            )
        # Check early close policy if active and before expiration date
        today = date.today()
        if sub.status == SubscriptionStatus.ACTIVE and sub.expiry_date and today < sub.expiry_date:
            if sub.plan and not sub.plan.allow_early_close:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Plan policy for '{sub.plan.name}' does not permit early closure before expiration.",
                )

        sub.status = SubscriptionStatus.CLOSED
        await record_audit_event(
            db,
            entity_type="subscription",
            entity_id=sub.id,
            action="CLOSE",
            actor_user_id=current_user.id,
            changes={"old_status": old_status.value, "new_status": sub.status.value, "reason": payload.reason},
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown status action '{payload.action}'. Supported: issue_quote, confirm, activate, pause, resume, renew, close.",
        )

    await db.commit()
    await db.refresh(sub, ["customer_account", "plan", "lines"])

    # Compute response
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
                product_variant_id=line.product_variant_id,
                variant_name=line.variant.name if line.variant else None,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rule_id=line.tax_rule_id,
                tax_rate=Decimal(str(line.tax_rule.rate_percentage)) if line.tax_rule else None,
                line_subtotal=_money(line_price),
            )
        )

    return SubscriptionResponse(
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
        total_amount=_money(total),
        lines=line_responses,
    )


@router.get(
    "/{subscription_id}/history",
    response_model=List[SubscriptionAuditItem],
    tags=["Subscriptions"],
)
async def get_subscription_history(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Retrieve full traceable status change and lifecycle audit history for this subscription."""
    exists = (
        await db.execute(select(Subscription.id).where(Subscription.id == subscription_id))
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found.")

    audit_query = (
        select(AuditEvent, User)
        .outerjoin(User, AuditEvent.actor_user_id == User.id)
        .where(
            AuditEvent.entity_type == "subscription",
            AuditEvent.entity_id == subscription_id,
        )
        .order_by(AuditEvent.timestamp.desc())
    )
    rows = (await db.execute(audit_query)).all()

    audit_items = []
    for event, actor in rows:
        audit_items.append(
            SubscriptionAuditItem(
                id=event.id,
                action=event.action,
                changes=event.changes_json or {},
                actor_user_id=event.actor_user_id,
                actor_name=actor.full_name if actor else "System",
                actor_email=actor.email if actor else None,
                actor_role=actor.role.value if actor else None,
                timestamp=event.timestamp,
            )
        )
    return audit_items


@router.post("/{subscription_id}/pause", tags=["Subscriptions"])
async def pause_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Pause an active subscription if plan policy permits."""
    return await transition_subscription_status(
        subscription_id=subscription_id,
        payload=SubscriptionStatusAction(action="pause"),
        db=db,
        current_user=_user,
    )


@router.post("/{subscription_id}/resume", tags=["Subscriptions"])
async def resume_subscription(
    subscription_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """Resume a paused subscription."""
    return await transition_subscription_status(
        subscription_id=subscription_id,
        payload=SubscriptionStatusAction(action="resume"),
        db=db,
        current_user=_user,
    )
