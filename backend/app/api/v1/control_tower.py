import uuid
from typing import List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.deps import require_admin, require_staff_or_admin
from app.core.database import get_db
from app.core.clock import organization_today
from app.models.user import User, UserRole
from app.models.billing_run import BillingRun, BillingRunItem, BillingRunStatus, BillingRunItemStatus
from app.models.subscription import Subscription
from app.schemas.billing_run import (
    CommitBatchRequest,
    CommitBatchResponse,
    ControlTowerItemResponse,
    ControlTowerPreviewResponse,
    BillingRunSummaryResponse,
    SkipItemRequest,
    RetryItemResponse,
    AutoBillResponse,
)
from app.services.billing import create_billing_preview, commit_billing_preview, recheck_preview_item
from app.services.audit import record_audit_event

router = APIRouter()


@router.post("/preview", response_model=ControlTowerPreviewResponse, tags=["Control Tower"])
async def preview_billing_batch(
    batch_size: int = Query(250, ge=1, le=500, description="Max subscriptions to evaluate in this batch"),
    db: AsyncSession = Depends(get_db),
    staff_user: User = Depends(require_staff_or_admin),
):
    """Persist a reviewable preview for a bounded batch of subscriptions due today."""
    run, rows = await create_billing_preview(
        db,
        actor_user_id=staff_user.id,
        as_of=organization_today(),
        batch_limit=batch_size,
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
            resulting_invoice_id=row.item.resulting_invoice_id,
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


@router.get("/runs/{billing_run_id}/export", tags=["Control Tower"])
async def export_billing_run_csv(
    billing_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """Export preview or run items as CSV for accounting/finance inspection."""
    import csv, io
    detail = await get_billing_run(billing_run_id, db=db, _user=_user)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Subscription #",
        "Customer Name",
        "Plan",
        "Period Start",
        "Period End",
        "Expected Subtotal",
        "Expected Tax",
        "Expected Discount",
        "Expected Total",
        "Prior Invoice Total",
        "Variance Amount",
        "Variance Reasons",
        "Warnings",
        "Status",
        "Skip Reason",
    ])
    for item in detail.items:
        writer.writerow([
            item.subscription_number,
            item.customer_name,
            item.plan_name,
            item.billing_period_start.isoformat(),
            item.billing_period_end.isoformat(),
            f"{item.expected_subtotal:.2f}",
            f"{item.expected_tax_amount:.2f}",
            f"{item.expected_discount_amount:.2f}",
            f"{item.expected_total_amount:.2f}",
            f"{item.prior_invoice_total:.2f}" if item.prior_invoice_total is not None else "0.00",
            f"{item.variance_amount:.2f}" if item.variance_amount is not None else "0.00",
            "; ".join(item.variance_reasons),
            "; ".join(item.warnings),
            item.status,
            item.skip_reason or "",
        ])
    csv_content = output.getvalue()
    today_str = organization_today().isoformat()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="billing_run_{billing_run_id}_{today_str}.csv"'},
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
        failed_count=await db.scalar(
            select(func.count(BillingRunItem.id)).where(
                BillingRunItem.billing_run_id == run.id,
                BillingRunItem.status == BillingRunItemStatus.FAILED,
            )
        ) or 0,
    )


@router.get("/runs", response_model=List[BillingRunSummaryResponse], tags=["Control Tower"])
async def list_billing_runs(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
    limit: int = Query(20, ge=1, le=100),
):
    """List historical billing runs with progress, projected amounts, and status breakdown."""
    query = (
        select(BillingRun)
        .options(selectinload(BillingRun.items))
        .order_by(BillingRun.created_at.desc())
        .limit(limit)
    )
    runs = (await db.execute(query)).scalars().all()
    summaries = []
    for r in runs:
        invoiced = sum(1 for it in r.items if it.status == BillingRunItemStatus.INVOICED)
        skipped = sum(1 for it in r.items if it.status == BillingRunItemStatus.SKIPPED)
        flagged = sum(1 for it in r.items if it.status == BillingRunItemStatus.FLAGGED)
        failed = sum(1 for it in r.items if it.status == BillingRunItemStatus.FAILED)
        summaries.append(
            BillingRunSummaryResponse(
                id=r.id,
                run_date=r.run_date,
                billing_period_start=r.billing_period_start,
                billing_period_end=r.billing_period_end,
                status=r.status.value,
                total_evaluated=r.total_evaluated,
                total_amount_projected=r.total_amount_projected,
                created_at=r.created_at,
                committed_at=r.committed_at,
                created_by_user_id=r.created_by_user_id,
                committed_by_user_id=r.committed_by_user_id,
                invoices_created_count=invoiced,
                skipped_count=skipped,
                flagged_count=flagged,
                failed_count=failed,
            )
        )
    return summaries


@router.get("/runs/{billing_run_id}", response_model=ControlTowerPreviewResponse, tags=["Control Tower"])
async def get_billing_run(
    billing_run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """Get complete details and per-subscription outcomes for a billing run."""
    query = (
        select(BillingRun)
        .where(BillingRun.id == billing_run_id)
        .options(
            selectinload(BillingRun.items)
            .selectinload(BillingRunItem.subscription)
            .selectinload(Subscription.customer_account),
            selectinload(BillingRun.items)
            .selectinload(BillingRunItem.subscription)
            .selectinload(Subscription.plan),
        )
    )
    run = (await db.execute(query)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Billing run not found.")

    items = [
        ControlTowerItemResponse(
            id=item.id,
            subscription_id=item.subscription_id,
            subscription_number=item.subscription.subscription_number if item.subscription else "Unknown",
            billing_period_start=item.billing_period_start,
            billing_period_end=item.billing_period_end,
            customer_name=(
                item.subscription.customer_account.company_name
                if item.subscription and item.subscription.customer_account
                else "Unknown"
            ),
            plan_name=item.subscription.plan.name if item.subscription and item.subscription.plan else "Standard",
            expected_subtotal=item.expected_subtotal,
            expected_tax_amount=item.expected_tax_amount,
            expected_discount_amount=item.expected_discount_amount,
            expected_total_amount=item.expected_total_amount,
            prior_invoice_total=item.prior_invoice_total,
            variance_amount=item.variance_amount,
            variance_reasons=item.variance_reasons or [],
            warnings=item.warnings or [],
            status=item.status,
            skip_reason=item.skip_reason,
            resulting_invoice_id=item.resulting_invoice_id,
        )
        for item in run.items
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


@router.get("/exceptions", response_model=List[ControlTowerItemResponse], tags=["Control Tower"])
async def list_exceptions(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_staff_or_admin),
):
    """List flagged and failed billing items needing review or retry."""
    query = (
        select(BillingRunItem)
        .where(BillingRunItem.status.in_([BillingRunItemStatus.FLAGGED, BillingRunItemStatus.FAILED]))
        .options(
            selectinload(BillingRunItem.subscription).selectinload(Subscription.customer_account),
            selectinload(BillingRunItem.subscription).selectinload(Subscription.plan),
        )
        .order_by(BillingRunItem.billing_period_start.desc())
        .limit(100)
    )
    items = (await db.execute(query)).scalars().all()
    return [
        ControlTowerItemResponse(
            id=item.id,
            subscription_id=item.subscription_id,
            subscription_number=item.subscription.subscription_number if item.subscription else "Unknown",
            billing_period_start=item.billing_period_start,
            billing_period_end=item.billing_period_end,
            customer_name=(
                item.subscription.customer_account.company_name
                if item.subscription and item.subscription.customer_account
                else "Unknown"
            ),
            plan_name=item.subscription.plan.name if item.subscription and item.subscription.plan else "Standard",
            expected_subtotal=item.expected_subtotal,
            expected_tax_amount=item.expected_tax_amount,
            expected_discount_amount=item.expected_discount_amount,
            expected_total_amount=item.expected_total_amount,
            prior_invoice_total=item.prior_invoice_total,
            variance_amount=item.variance_amount,
            variance_reasons=item.variance_reasons or [],
            warnings=item.warnings or [],
            status=item.status,
            skip_reason=item.skip_reason,
            resulting_invoice_id=item.resulting_invoice_id,
        )
        for item in items
    ]


@router.post("/items/{item_id}/retry", response_model=RetryItemResponse, tags=["Control Tower"])
async def retry_flagged_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    """
    Re-evaluate a flagged item after resolving customer tax ID, plan issues, or pricing rules.
    If warnings clear, moves status back to pending.
    """
    item = await recheck_preview_item(db, item_id=item_id, actor_user_id=user.id)
    run = await db.get(BillingRun, item.billing_run_id)
    if (
        user.role == UserRole.ADMIN
        and item.status == BillingRunItemStatus.PENDING
        and run
        and run.status in (
            BillingRunStatus.COMMITTED,
            BillingRunStatus.FAILED,
        )
    ):
        await commit_billing_preview(
            db,
            billing_run_id=run.id,
            approved_item_ids=[item.id],
            actor_user_id=user.id,
            as_of=organization_today(),
        )
        await db.refresh(item)
    msg = (
        "Issues resolved and an invoice is now attached to this run."
        if item.status == BillingRunItemStatus.INVOICED
        else "Issue resolved; an administrator or the next scheduled billing run can now retry it."
        if item.status == BillingRunItemStatus.PENDING and run and run.status in (
            BillingRunStatus.COMMITTED,
            BillingRunStatus.FAILED,
        )
        else "Item re-evaluated. Issues resolved and marked clean for billing."
        if item.status == BillingRunItemStatus.PENDING
        else f"Item re-evaluated with {len(item.warnings)} warning(s) remaining."
    )
    return RetryItemResponse(
        id=item.id,
        subscription_id=item.subscription_id,
        status=item.status,
        warnings=item.warnings or [],
        expected_total_amount=item.expected_total_amount,
        message=msg,
    )


@router.post("/items/{item_id}/skip", response_model=ControlTowerItemResponse, tags=["Control Tower"])
async def skip_item(
    item_id: uuid.UUID,
    payload: SkipItemRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff_or_admin),
):
    """Explicitly skip a billing item with an audit reason."""
    query = (
        select(BillingRunItem)
        .where(BillingRunItem.id == item_id)
        .options(
            selectinload(BillingRunItem.subscription).selectinload(Subscription.customer_account),
            selectinload(BillingRunItem.subscription).selectinload(Subscription.plan),
        )
    )
    item = (await db.execute(query)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Billing run item not found.")
    if item.status not in (
        BillingRunItemStatus.PENDING,
        BillingRunItemStatus.FLAGGED,
        BillingRunItemStatus.FAILED,
    ):
        raise HTTPException(status_code=409, detail="Only pending, flagged, or failed items can be skipped.")

    item.status = BillingRunItemStatus.SKIPPED
    item.skip_reason = payload.reason.strip()
    if item.billing_run_id:
        run = await db.get(BillingRun, item.billing_run_id)
        if run and run.status == BillingRunStatus.FAILED:
            remaining_failures = await db.scalar(
                select(func.count(BillingRunItem.id)).where(
                    BillingRunItem.billing_run_id == run.id,
                    BillingRunItem.status == BillingRunItemStatus.FAILED,
                    BillingRunItem.id != item.id,
                )
            ) or 0
            if not remaining_failures:
                run.status = BillingRunStatus.COMMITTED
    await record_audit_event(
        db,
        entity_type="billing_run_item",
        entity_id=item.id,
        action="SKIP",
        actor_user_id=user.id,
        changes={"status": item.status.value, "skip_reason": item.skip_reason},
    )
    await db.commit()
    await db.refresh(item)
    return ControlTowerItemResponse(
        id=item.id,
        subscription_id=item.subscription_id,
        subscription_number=item.subscription.subscription_number if item.subscription else "Unknown",
        billing_period_start=item.billing_period_start,
        billing_period_end=item.billing_period_end,
        customer_name=(
            item.subscription.customer_account.company_name
            if item.subscription and item.subscription.customer_account
            else "Unknown"
        ),
        plan_name=item.subscription.plan.name if item.subscription and item.subscription.plan else "Standard",
        expected_subtotal=item.expected_subtotal,
        expected_tax_amount=item.expected_tax_amount,
        expected_discount_amount=item.expected_discount_amount,
        expected_total_amount=item.expected_total_amount,
        prior_invoice_total=item.prior_invoice_total,
        variance_amount=item.variance_amount,
        variance_reasons=item.variance_reasons or [],
        warnings=item.warnings or [],
        status=item.status,
        skip_reason=item.skip_reason,
        resulting_invoice_id=item.resulting_invoice_id,
    )


@router.post("/auto-bill", response_model=AutoBillResponse, tags=["Control Tower"])
async def trigger_auto_billing(
    _user: User = Depends(require_admin),
):
    """
    Queue recurring billing in the background so the web request returns immediately.
    """
    from app.worker import generate_recurring_invoices
    task = generate_recurring_invoices.delay()
    return AutoBillResponse(
        status="queued",
        task_id=task.id,
    )
