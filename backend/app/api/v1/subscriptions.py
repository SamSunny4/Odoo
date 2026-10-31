import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.customer import CustomerAccount
from app.models.plan import Plan
from app.models.catalog import Product, ProductVariant
from app.schemas.subscription import SubscriptionResponse, SubscriptionLineResponse
from app.api.v1.deps import require_staff_or_admin
from app.services.audit import record_audit_event

router = APIRouter()


@router.get("", response_model=List[SubscriptionResponse], tags=["Subscriptions"])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_staff_or_admin),
):
    """
    List all subscriptions for admin/staff operations.
    Calculates period total from base price and product lines with variants.
    """
    query = (
        select(Subscription)
        .options(
            selectinload(Subscription.customer_account),
            selectinload(Subscription.plan),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
            selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
        )
        .order_by(Subscription.created_at.desc())
    )
    result = await db.execute(query)
    subscriptions = result.scalars().all()

    response = []
    for sub in subscriptions:
        # Calculate total
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

        response.append(
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
    return response


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
