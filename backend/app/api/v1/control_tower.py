import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_admin, require_staff_or_admin
from app.core.database import get_db
from app.core.clock import organization_today
from app.models.user import User
from app.schemas.billing_run import (
    CommitBatchRequest,
    CommitBatchResponse,
    ControlTowerItemResponse,
    ControlTowerPreviewResponse,
)
from app.services.billing import create_billing_preview, commit_billing_preview

router = APIRouter()


@router.post("/preview", response_model=ControlTowerPreviewResponse, tags=["Control Tower"])
async def preview_billing_batch(
    db: AsyncSession = Depends(get_db),
    staff_user: User = Depends(require_staff_or_admin),
):
    """Persist a reviewable preview for subscriptions due as of today."""
    run, rows = await create_billing_preview(
        db,
        actor_user_id=staff_user.id,
        as_of=organization_today(),
    )
    items = [
        ControlTowerItemResponse(
            id=row.item.id,
            subscription_id=row.subscription.id,
            subscription_number=row.subscription.subscription_number,
            billing_period_start=row.item.billing_period_start,
            billing_period_end=row.item.billing_period_end,
            customer_name=(row.subscription.customer_account.company_name
                           if row.subscription.customer_account else "Unknown"),
            plan_name=row.subscription.plan.name if row.subscription.plan else "Standard",
            expected_subtotal=row.charge.subtotal,
            expected_tax_amount=row.charge.tax,
            expected_discount_amount=row.charge.discount,
            expected_total_amount=row.charge.total,
            prior_invoice_total=row.item.prior_invoice_total,
            variance_amount=row.item.variance_amount,
            variance_reasons=row.item.variance_reasons,
            warnings=row.item.warnings,
            status=row.item.status,
            skip_reason=row.item.skip_reason,
        )
        for row in rows
    ]
    return ControlTowerPreviewResponse(
        billing_run_id=run.id,
        billing_period_start=run.billing_period_start,
        billing_period_end=run.billing_period_end,
        total_subscriptions=len(items),
        total_projected_amount=run.total_amount_projected,
        flagged_count=sum(bool(item.warnings) for item in items),
        items=items,
    )


@router.post("/runs/{billing_run_id}/commit", response_model=CommitBatchResponse, tags=["Control Tower"])
async def commit_billing_batch(
    billing_run_id: uuid.UUID,
    payload: CommitBatchRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    """Commit only the clean preview items explicitly selected by an admin."""
    run, invoices = await commit_billing_preview(
        db,
        billing_run_id=billing_run_id,
        approved_item_ids=payload.approved_item_ids,
        actor_user_id=admin_user.id,
        as_of=organization_today(),
    )
    return CommitBatchResponse(
        billing_run_id=run.id,
        invoices_created_count=len(invoices),
        total_invoiced_amount=sum((invoice.total_amount for invoice in invoices), start=Decimal("0.00")),
        status=run.status.value,
    )
