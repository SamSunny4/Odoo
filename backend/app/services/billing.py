"""Shared recurring-billing calculations and persisted preview/commit workflow."""

import calendar
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.billing_run import BillingRun, BillingRunItem, BillingRunItemStatus, BillingRunStatus
from app.models.catalog import Product, ProductVariant
from app.models.customer import CustomerAccount
from app.models.discount import DiscountRedemption, DiscountRule, DiscountScope, DiscountType
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus, SendStatus
from app.models.plan import BillingCadence
from app.models.subscription import Subscription, SubscriptionLine, SubscriptionStatus
from app.models.tax import TaxRule
from app.services.audit import record_audit_event
from app.services.outbox import create_outbox_message

CENT = Decimal("0.01")


@dataclass
class ChargeLine:
    description: str
    product_name: str
    variant_name: Optional[str]
    product_id: Optional[uuid.UUID]
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    discount: Decimal
    tax_name: Optional[str]
    tax_rate: Decimal
    tax_amount: Decimal
    line_total: Decimal


@dataclass
class SubscriptionCharge:
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    discount_rule: Optional[DiscountRule]
    lines: list[ChargeLine]
    warnings: list[str]


@dataclass
class PreviewRow:
    item: BillingRunItem
    subscription: Subscription
    charge: SubscriptionCharge


def compute_next_billing_date(current_date: date, cadence: BillingCadence, anchor_day: int) -> date:
    """Advance a billing date while preserving monthly/yearly anchors."""
    if cadence == BillingCadence.DAILY:
        return current_date + timedelta(days=1)
    if cadence == BillingCadence.WEEKLY:
        return current_date + timedelta(days=7)
    if cadence == BillingCadence.MONTHLY:
        year = current_date.year + (current_date.month // 12)
        month = (current_date.month % 12) + 1
    elif cadence == BillingCadence.YEARLY:
        year = current_date.year + 1
        month = current_date.month
    else:
        raise ValueError(f"Unsupported billing cadence: {cadence}")
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, min(anchor_day, last_day))


def billing_period_end(start: date, cadence: BillingCadence, anchor_day: int) -> date:
    return compute_next_billing_date(start, cadence, anchor_day) - timedelta(days=1)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


async def generate_invoice_number(db: AsyncSession, year: int) -> str:
    """Generate collision-free human-readable sequential invoice number (e.g. INV-2026-0001)."""
    # Serialize number allocation on PostgreSQL. The unique column remains the
    # final guard, while the transaction lock prevents concurrent count+1 races.
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(734821906)))
    count_query = select(func.count(Invoice.id)).where(
        Invoice.invoice_number.like(f"INV-{year}-%")
    )
    total_count = (await db.execute(count_query)).scalar_one()
    seq = total_count + 1
    while True:
        candidate = f"INV-{year}-{seq:04d}"
        exists = (await db.execute(
            select(Invoice.id).where(Invoice.invoice_number == candidate)
        )).scalar_one_or_none()
        if not exists:
            return candidate
        seq += 1


def calculate_subscription_charge(
    subscription: Subscription,
    *,
    tax_map: dict[uuid.UUID, TaxRule],
    default_tax_rule: Optional[TaxRule],
    discount_rules: list[DiscountRule],
    redemption_counts: dict[uuid.UUID, int],
    as_of: date,
) -> SubscriptionCharge:
    """Apply one deterministic pricing/tax/discount calculation to all billing paths."""
    raw_lines: list[dict] = []
    warnings: list[str] = []
    plan = subscription.plan

    if plan:
        raw_lines.append({
            "description": f"Plan Base Fee — {plan.name}",
            "product_name": plan.name,
            "variant_name": None,
            "product_id": None,
            "quantity": 1,
            "unit_price": Decimal(str(plan.base_price)),
            "subtotal": Decimal(str(plan.base_price)),
            "tax_rule_id": None,
        })
        if not plan.is_active:
            warnings.append("The selected plan is inactive.")

    total_quantity = 0
    for line in subscription.lines:
        unit_price = Decimal(str(line.unit_price))
        raw_lines.append({
            "description": line.product.name if line.product else "Product Line",
            "product_name": line.product.name if line.product else "Product",
            "variant_name": line.variant.name if line.variant else None,
            "product_id": line.product_id,
            "quantity": line.quantity,
            "unit_price": unit_price,
            "subtotal": _money(unit_price * line.quantity),
            "tax_rule_id": line.tax_rule_id,
        })
        total_quantity += line.quantity

    gross_subtotal = sum((line["subtotal"] for line in raw_lines), Decimal("0.00"))

    if plan and total_quantity < plan.min_quantity:
        warnings.append(f"Quantity {total_quantity} is below the plan minimum of {plan.min_quantity}.")

    best_rule: Optional[DiscountRule] = None
    best_indices: list[int] = []
    best_amount = Decimal("0.00")
    for rule in discount_rules:
        if not rule.is_active or not (rule.valid_from <= as_of <= rule.valid_to):
            continue

        if rule.scope == DiscountScope.SUBSCRIPTION:
            eligible_indices = list(range(len(raw_lines)))
        elif rule.scope == DiscountScope.PRODUCT and rule.target_product_id:
            eligible_indices = [
                index for index, line in enumerate(raw_lines)
                if line["product_id"] == rule.target_product_id
            ]
        else:
            continue

        if not eligible_indices:
            continue
        eligible_subtotal = sum((raw_lines[i]["subtotal"] for i in eligible_indices), Decimal("0.00"))
        eligible_quantity = sum(raw_lines[i]["quantity"] for i in eligible_indices)
        if eligible_subtotal < rule.min_spend or eligible_quantity < rule.min_quantity:
            continue

        used = redemption_counts.get(rule.id, 0)
        if rule.max_usage_limit is not None and used >= rule.max_usage_limit:
            warnings.append(f"Discount '{rule.name}' has reached its usage limit.")
            continue

        if rule.discount_type == DiscountType.PERCENTAGE:
            amount = _money(eligible_subtotal * Decimal(str(rule.value)) / Decimal("100"))
        else:
            amount = min(eligible_subtotal, Decimal(str(rule.value)))
        if amount > best_amount:
            best_rule = rule
            best_indices = eligible_indices
            best_amount = amount

    discounts = [Decimal("0.00") for _ in raw_lines]
    eligible_basis = sum((raw_lines[i]["subtotal"] for i in best_indices), Decimal("0.00"))
    remaining_discount = best_amount
    for position, index in enumerate(best_indices):
        base = raw_lines[index]["subtotal"]
        if position == len(best_indices) - 1:
            allocation = remaining_discount
        elif eligible_basis > 0:
            allocation = _money(best_amount * base / eligible_basis)
        else:
            allocation = Decimal("0.00")
        allocation = min(base, max(Decimal("0.00"), allocation), remaining_discount)
        discounts[index] = allocation
        remaining_discount -= allocation

    invoice_lines: list[ChargeLine] = []
    total_tax = Decimal("0.00")
    for index, line in enumerate(raw_lines):
        rule = tax_map.get(line["tax_rule_id"]) if line["tax_rule_id"] else default_tax_rule
        if line["tax_rule_id"] and rule is None:
            warnings.append(f"Tax rule for '{line['description']}' is inactive or missing.")
        elif rule is None and tax_map:
            warnings.append(f"Assign a tax rule to '{line['description']}' before billing.")

        rate = Decimal(str(rule.rate_percentage)) if rule else Decimal("0.00")
        tax_base = max(Decimal("0.00"), line["subtotal"] - discounts[index])
        line_tax = _money(tax_base * rate / Decimal("100"))
        total_tax += line_tax
        invoice_lines.append(ChargeLine(
            description=line["description"] + (f" ({line['variant_name']})" if line["variant_name"] else ""),
            product_name=line["product_name"],
            variant_name=line["variant_name"],
            product_id=line["product_id"],
            quantity=line["quantity"],
            unit_price=line["unit_price"],
            subtotal=line["subtotal"],
            discount=discounts[index],
            tax_name=rule.name if rule else None,
            tax_rate=rate,
            tax_amount=line_tax,
            line_total=tax_base + line_tax,
        ))

    total_discount = sum(discounts, Decimal("0.00"))
    return SubscriptionCharge(
        subtotal=gross_subtotal,
        discount=total_discount,
        tax=total_tax,
        total=max(Decimal("0.00"), gross_subtotal - total_discount + total_tax),
        discount_rule=best_rule,
        lines=invoice_lines,
        warnings=list(dict.fromkeys(warnings)),
    )


def _subscription_options():
    return (
        selectinload(Subscription.customer_account),
        selectinload(Subscription.plan),
        selectinload(Subscription.lines).selectinload(SubscriptionLine.product),
        selectinload(Subscription.lines).selectinload(SubscriptionLine.variant),
    )


async def _load_pricing_rules(db: AsyncSession, *, lock_discounts: bool = False):
    tax_rules = (await db.execute(
        select(TaxRule).where(TaxRule.is_active.is_(True)).order_by(TaxRule.name)
    )).scalars().all()
    tax_map = {rule.id: rule for rule in tax_rules}
    default_tax_rule = tax_rules[0] if len(tax_rules) == 1 else None

    discount_query = select(DiscountRule).where(DiscountRule.is_active.is_(True)).order_by(DiscountRule.id)
    if lock_discounts:
        discount_query = discount_query.with_for_update()
    discount_rules = (await db.execute(discount_query)).scalars().all()
    counts_rows = (await db.execute(
        select(DiscountRedemption.discount_rule_id, func.count(DiscountRedemption.id))
        .group_by(DiscountRedemption.discount_rule_id)
    )).all()
    redemption_counts = {rule_id: count for rule_id, count in counts_rows}
    return tax_map, default_tax_rule, discount_rules, redemption_counts


async def create_billing_preview(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    as_of: date,
    batch_limit: Optional[int] = None,
    subscription_ids: Optional[list[uuid.UUID]] = None,
) -> tuple[BillingRun, list[PreviewRow]]:
    due_date_expr = func.coalesce(Subscription.next_billing_date, Subscription.start_date)
    query = (
        select(Subscription)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE,
            due_date_expr <= as_of,
        )
        .options(*_subscription_options())
        .order_by(due_date_expr, Subscription.subscription_number)
    )
    if subscription_ids is not None:
        query = query.where(Subscription.id.in_(subscription_ids))
    if batch_limit and batch_limit > 0:
        query = query.limit(batch_limit)
    subscriptions = (await db.execute(query)).scalars().all()
    tax_map, default_tax_rule, rules, counts = await _load_pricing_rules(db)

    prior_by_subscription: dict[uuid.UUID, Invoice] = {}
    if subscriptions:
        ranked_prior_invoices = (
            select(
                Invoice.id.label("invoice_id"),
                Invoice.subscription_id.label("subscription_id"),
                func.row_number().over(
                    partition_by=Invoice.subscription_id,
                    order_by=(Invoice.issue_date.desc(), Invoice.created_at.desc(), Invoice.id.desc()),
                ).label("row_number"),
            )
            .where(Invoice.subscription_id.in_([subscription.id for subscription in subscriptions]))
            .subquery()
        )
        latest_rows = (await db.execute(
            select(Invoice).join(ranked_prior_invoices, Invoice.id == ranked_prior_invoices.c.invoice_id)
            .where(ranked_prior_invoices.c.row_number == 1)
        )).scalars().all()
        prior_by_subscription = {invoice.subscription_id: invoice for invoice in latest_rows}

    prepared: list[tuple[Subscription, date, date, SubscriptionCharge, Optional[Invoice]]] = []
    for subscription in subscriptions:
        period_start = subscription.next_billing_date or subscription.start_date
        if subscription.expiry_date and period_start > subscription.expiry_date:
            continue
        cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
        period_end = billing_period_end(period_start, cadence, subscription.billing_anchor_day)
        charge = calculate_subscription_charge(
            subscription,
            tax_map=tax_map,
            default_tax_rule=default_tax_rule,
            discount_rules=rules,
            redemption_counts=counts,
            as_of=period_start,
        )
        if subscription.customer_account and not subscription.customer_account.tax_id and tax_map:
            charge.warnings.append("Customer tax ID is missing.")
        prior = prior_by_subscription.get(subscription.id)
        prepared.append((subscription, period_start, period_end, charge, prior))
        if charge.discount_rule and not charge.warnings:
            counts[charge.discount_rule.id] = counts.get(charge.discount_rule.id, 0) + 1

    period_start = min((row[1] for row in prepared), default=as_of)
    period_end = max((row[2] for row in prepared), default=as_of)
    run = BillingRun(
        run_date=as_of,
        billing_period_start=period_start,
        billing_period_end=period_end,
        status=BillingRunStatus.PREVIEW,
        total_evaluated=len(prepared),
        total_amount_projected=sum((row[3].total for row in prepared), Decimal("0.00")),
        created_by_user_id=actor_user_id,
    )
    db.add(run)
    await db.flush()

    rows: list[PreviewRow] = []
    for subscription, start, end, charge, prior in prepared:
        variance = charge.total - prior.total_amount if prior else Decimal("0.00")
        item = BillingRunItem(
            billing_run_id=run.id,
            subscription_id=subscription.id,
            billing_period_start=start,
            billing_period_end=end,
            expected_subtotal=charge.subtotal,
            expected_tax_amount=charge.tax,
            expected_discount_amount=charge.discount,
            expected_total_amount=charge.total,
            prior_invoice_id=prior.id if prior else None,
            prior_invoice_total=prior.total_amount if prior else None,
            variance_amount=variance,
            variance_reasons=[f"Total changed by {variance:+.2f} compared with the latest invoice."] if variance else [],
            warnings=charge.warnings,
            status=BillingRunItemStatus.FLAGGED if charge.warnings else BillingRunItemStatus.PENDING,
        )
        db.add(item)
        rows.append(PreviewRow(item, subscription, charge))

    await db.commit()
    return run, rows


async def _commit_billing_preview_impl(
    db: AsyncSession,
    *,
    billing_run_id: uuid.UUID,
    approved_item_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    as_of: date,
    allow_empty: bool = False,
) -> tuple[BillingRun, list[Invoice]]:
    if not approved_item_ids and not allow_empty:
        raise HTTPException(status_code=400, detail="Select at least one clean subscription to bill.")

    run = (await db.execute(
        select(BillingRun).where(BillingRun.id == billing_run_id).with_for_update()
    )).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Billing preview not found.")
    if run.status not in (BillingRunStatus.PREVIEW, BillingRunStatus.COMMITTED, BillingRunStatus.FAILED):
        raise HTTPException(status_code=409, detail="This billing run cannot be committed in its current state.")
    previous_status = run.status

    all_items = (await db.execute(
        select(BillingRunItem)
        .where(BillingRunItem.billing_run_id == run.id)
        .join(Subscription, Subscription.id == BillingRunItem.subscription_id)
        .order_by(BillingRunItem.billing_period_start, Subscription.subscription_number)
        .with_for_update()
    )).scalars().all()
    item_map = {item.id: item for item in all_items}
    selected_ids = set(approved_item_ids)
    if not selected_ids.issubset(item_map):
        raise HTTPException(status_code=400, detail="One or more selected items are not part of this preview.")
    selected_items = [item for item in all_items if item.id in selected_ids]
    if any(item.status != BillingRunItemStatus.PENDING for item in selected_items):
        raise HTTPException(status_code=400, detail="Flagged or previously processed items cannot be committed.")

    for item in all_items:
        if (
            previous_status == BillingRunStatus.PREVIEW
            and item.status == BillingRunItemStatus.PENDING
            and item.id not in selected_ids
        ):
            item.status = BillingRunItemStatus.SKIPPED
            item.skip_reason = "Not selected for this billing commit."

    if not selected_items:
        if previous_status == BillingRunStatus.PREVIEW:
            run.status = BillingRunStatus.COMMITTED
            run.committed_by_user_id = actor_user_id
            run.committed_at = datetime.now(timezone.utc)
            await db.commit()
        return run, []

    subscription_ids = [item.subscription_id for item in selected_items]
    subscriptions = (await db.execute(
        select(Subscription)
        .where(Subscription.id.in_(subscription_ids))
        .options(*_subscription_options())
        .with_for_update()
    )).scalars().all()
    sub_map = {sub.id: sub for sub in subscriptions}
    tax_map, default_tax_rule, rules, counts = await _load_pricing_rules(db, lock_discounts=True)
    created_invoices: list[Invoice] = []
    total_committed = Decimal("0.00")

    for sequence, item in enumerate(selected_items, start=1):
        subscription = sub_map.get(item.subscription_id)
        if not subscription or subscription.status != SubscriptionStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="A selected subscription is no longer active. Refresh the preview.")

        current_due = subscription.next_billing_date or subscription.start_date
        if current_due != item.billing_period_start or current_due > as_of:
            raise HTTPException(status_code=409, detail="A selected subscription changed after preview. Refresh the preview.")

        cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
        expected_end = billing_period_end(current_due, cadence, subscription.billing_anchor_day)
        if expected_end != item.billing_period_end:
            raise HTTPException(status_code=409, detail="A selected billing period changed after preview. Refresh the preview.")

        charge = calculate_subscription_charge(
            subscription,
            tax_map=tax_map,
            default_tax_rule=default_tax_rule,
            discount_rules=rules,
            redemption_counts=counts,
            as_of=item.billing_period_start,
        )
        if charge.warnings or (
            charge.subtotal != item.expected_subtotal
            or charge.tax != item.expected_tax_amount
            or charge.discount != item.expected_discount_amount
            or charge.total != item.expected_total_amount
        ):
            raise HTTPException(status_code=409, detail="Pricing or eligibility changed after preview. Refresh the preview.")

        idempotency_key = f"sub_{subscription.id}_{item.billing_period_start.isoformat()}_{item.billing_period_end.isoformat()}"
        existing = (await db.execute(
            select(Invoice).where(Invoice.idempotency_key == idempotency_key)
        )).scalar_one_or_none()
        if existing:
            item.status = BillingRunItemStatus.INVOICED
            item.resulting_invoice_id = existing.id
            subscription.next_billing_date = compute_next_billing_date(
                item.billing_period_start, cadence, subscription.billing_anchor_day
            )
            continue

        invoice_lines = [
            InvoiceLine(
                description=line.description,
                product_name_snapshot=line.product_name,
                variant_name_snapshot=line.variant_name,
                quantity=line.quantity,
                unit_price_snapshot=line.unit_price,
                subtotal=line.subtotal,
                tax_rule_name_snapshot=line.tax_name,
                tax_rate_snapshot=line.tax_rate,
                tax_amount=line.tax_amount,
                discount_rule_name_snapshot=charge.discount_rule.name if charge.discount_rule and line.discount else None,
                discount_amount=line.discount,
                line_total=line.line_total,
            )
            for line in charge.lines
        ]
        account = subscription.customer_account
        inv_num = await generate_invoice_number(db, as_of.year)
        invoice = Invoice(
            invoice_number=inv_num,
            subscription_id=subscription.id,
            customer_account_id=subscription.customer_account_id,
            billing_run_id=run.id,
            idempotency_key=idempotency_key,
            currency=account.currency if account else settings.ORGANIZATION_CURRENCY,
            status=InvoiceStatus.CONFIRMED,
            billing_period_start=item.billing_period_start,
            billing_period_end=item.billing_period_end,
            subtotal=charge.subtotal,
            tax_amount=charge.tax,
            discount_amount=charge.discount,
            total_amount=charge.total,
            paid_amount=Decimal("0.00"),
            issue_date=as_of,
            due_date=as_of + timedelta(days=subscription.payment_terms_days),
            send_status=SendStatus.NOT_SENT,
            customer_snapshot={
                "company_name": account.company_name if account else "Customer",
                "billing_email": account.billing_email if account else "",
                "tax_id": account.tax_id if account else None,
            },
            billing_address_snapshot={
                "address_line1": account.billing_address_line1 if account else "",
                "address_line2": account.billing_address_line2 if account else None,
                "city": account.billing_city if account else "",
                "state": account.billing_state if account else None,
                "postal_code": account.billing_postal_code if account else "",
                "country": account.billing_country if account else "",
            },
            lines=invoice_lines,
        )
        db.add(invoice)
        await db.flush()
        if charge.discount_rule:
            db.add(DiscountRedemption(
                discount_rule_id=charge.discount_rule.id,
                invoice_id=invoice.id,
                subscription_id=subscription.id,
            ))
            counts[charge.discount_rule.id] = counts.get(charge.discount_rule.id, 0) + 1

        subscription.next_billing_date = compute_next_billing_date(
            item.billing_period_start, cadence, subscription.billing_anchor_day
        )
        item.status = BillingRunItemStatus.INVOICED
        item.resulting_invoice_id = invoice.id
        total_committed += charge.total
        created_invoices.append(invoice)
        await record_audit_event(
            db,
            entity_type="invoice",
            entity_id=invoice.id,
            action="CREATE",
            actor_user_id=actor_user_id,
            changes={"invoice_number": invoice.invoice_number, "total_amount": str(invoice.total_amount)},
        )
        if account and account.billing_email:
            invoice.send_status = SendStatus.QUEUED
            await create_outbox_message(
                db,
                topic="email",
                payload={
                    "type": "invoice_issued",
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "recipient_email": account.billing_email,
                    "total_amount": str(invoice.total_amount),
                    "due_date": invoice.due_date.isoformat(),
                },
            )

    has_failed_items = any(item.status == BillingRunItemStatus.FAILED for item in all_items)
    run.status = BillingRunStatus.FAILED if has_failed_items else BillingRunStatus.COMMITTED
    run.committed_by_user_id = actor_user_id
    run.committed_at = datetime.now(timezone.utc)
    await record_audit_event(
        db,
        entity_type="billing_run",
        entity_id=run.id,
        action="COMMIT",
        actor_user_id=actor_user_id,
        changes={"invoices_created": len(created_invoices), "total_amount": str(total_committed)},
    )
    await db.commit()
    return run, created_invoices


async def commit_billing_preview(
    db: AsyncSession,
    *,
    billing_run_id: uuid.UUID,
    approved_item_ids: list[uuid.UUID],
    actor_user_id: uuid.UUID,
    as_of: date,
    allow_empty: bool = False,
) -> tuple[BillingRun, list[Invoice]]:
    """Commit a billing batch and persist unexpected per-item failures for retry."""
    try:
        return await _commit_billing_preview_impl(
            db,
            billing_run_id=billing_run_id,
            approved_item_ids=approved_item_ids,
            actor_user_id=actor_user_id,
            as_of=as_of,
            allow_empty=allow_empty,
        )
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        run = (await db.execute(
            select(BillingRun).where(BillingRun.id == billing_run_id).with_for_update()
        )).scalar_one_or_none()
        if not run:
            raise

        selected_items = (await db.execute(
            select(BillingRunItem)
            .where(
                BillingRunItem.billing_run_id == billing_run_id,
                BillingRunItem.id.in_(approved_item_ids),
            )
            .with_for_update()
        )).scalars().all()
        failure_reason = f"Billing attempt failed ({type(exc).__name__}): {str(exc)[:400]}"
        for item in selected_items:
            if item.status in (BillingRunItemStatus.PENDING, BillingRunItemStatus.FAILED):
                item.status = BillingRunItemStatus.FAILED
                item.warnings = list(item.warnings or []) + [failure_reason]
        run.status = BillingRunStatus.FAILED
        await record_audit_event(
            db,
            entity_type="billing_run",
            entity_id=run.id,
            action="COMMIT_FAILED",
            actor_user_id=actor_user_id,
            changes={"failed_item_count": len(selected_items), "reason": failure_reason},
        )
        await db.commit()
        return run, []


async def generate_invoice_for_subscription(
    db: AsyncSession,
    *,
    subscription_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    as_of: date,
    as_draft: bool = True,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> Invoice:
    """
    Generate an invoice draft or confirmed invoice directly from a subscription.
    Enforces idempotency, calculates taxes & discounts, freezes customer & line snapshots.
    """
    query = (
        select(Subscription)
        .where(Subscription.id == subscription_id)
        .options(*_subscription_options())
        .with_for_update()
    )
    subscription = (await db.execute(query)).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")

    if subscription.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.CONFIRMED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate invoice for subscription with status '{subscription.status.value}'. Must be active or confirmed.",
        )

    start = period_start or subscription.next_billing_date or subscription.start_date
    cadence = subscription.plan.cadence if subscription.plan else BillingCadence.MONTHLY
    end = period_end or billing_period_end(start, cadence, subscription.billing_anchor_day)
    current_due = subscription.next_billing_date or subscription.start_date
    if end < start:
        raise HTTPException(status_code=422, detail="Billing period end must be on or after its start date.")
    if start > current_due:
        raise HTTPException(
            status_code=409,
            detail="A later billing period cannot be invoiced while an earlier period is still due.",
        )
    if end != billing_period_end(start, cadence, subscription.billing_anchor_day):
        raise HTTPException(status_code=422, detail="Billing period dates do not match the subscription cadence.")

    idempotency_key = f"sub_{subscription.id}_{start.isoformat()}_{end.isoformat()}"
    existing = (await db.execute(
        select(Invoice).where(Invoice.idempotency_key == idempotency_key)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An invoice ({existing.invoice_number}) has already been generated for subscription {subscription.subscription_number} for period {start} to {end}.",
        )

    overlapping = (await db.execute(
        select(Invoice.id).where(
            Invoice.subscription_id == subscription.id,
            Invoice.billing_period_start <= end,
            Invoice.billing_period_end >= start,
        ).limit(1)
    )).scalar_one_or_none()
    if overlapping:
        raise HTTPException(status_code=409, detail="An invoice already exists for an overlapping billing period.")

    tax_map, default_tax_rule, rules, counts = await _load_pricing_rules(db, lock_discounts=not as_draft)
    charge = calculate_subscription_charge(
        subscription,
        tax_map=tax_map,
        default_tax_rule=default_tax_rule,
        discount_rules=rules,
        redemption_counts=counts,
        as_of=start,
    )

    account = subscription.customer_account
    invoice_num = await generate_invoice_number(db, as_of.year)

    invoice_lines = [
        InvoiceLine(
            description=line.description,
            product_name_snapshot=line.product_name,
            variant_name_snapshot=line.variant_name,
            quantity=line.quantity,
            unit_price_snapshot=line.unit_price,
            subtotal=line.subtotal,
            tax_rule_name_snapshot=line.tax_name,
            tax_rate_snapshot=line.tax_rate,
            tax_amount=line.tax_amount,
            discount_rule_name_snapshot=charge.discount_rule.name if charge.discount_rule and line.discount else None,
            discount_amount=line.discount,
            line_total=line.line_total,
        )
        for line in charge.lines
    ]

    inv_status = InvoiceStatus.DRAFT if as_draft else InvoiceStatus.CONFIRMED
    invoice = Invoice(
        invoice_number=invoice_num,
        subscription_id=subscription.id,
        customer_account_id=subscription.customer_account_id,
        billing_run_id=None,
        idempotency_key=idempotency_key,
        currency=account.currency if account else settings.ORGANIZATION_CURRENCY,
        status=inv_status,
        billing_period_start=start,
        billing_period_end=end,
        subtotal=charge.subtotal,
        tax_amount=charge.tax,
        discount_amount=charge.discount,
        total_amount=charge.total,
        paid_amount=Decimal("0.00"),
        issue_date=as_of,
        due_date=as_of + timedelta(days=subscription.payment_terms_days),
        send_status=SendStatus.NOT_SENT,
        customer_snapshot={
            "company_name": account.company_name if account else "Customer",
            "billing_email": account.billing_email if account else "",
            "tax_id": account.tax_id if account else None,
        },
        billing_address_snapshot={
            "address_line1": account.billing_address_line1 if account else "",
            "address_line2": account.billing_address_line2 if account else None,
            "city": account.billing_city if account else "",
            "state": account.billing_state if account else None,
            "postal_code": account.billing_postal_code if account else "",
            "country": account.billing_country if account else "",
        },
        lines=invoice_lines,
    )
    db.add(invoice)
    await db.flush()

    if not as_draft and start == current_due:
        if charge.discount_rule:
            db.add(DiscountRedemption(
                discount_rule_id=charge.discount_rule.id,
                invoice_id=invoice.id,
                subscription_id=subscription.id,
            ))
        subscription.next_billing_date = compute_next_billing_date(start, cadence, subscription.billing_anchor_day)

    await record_audit_event(
        db,
        entity_type="invoice",
        entity_id=invoice.id,
        action="CREATE_DRAFT" if as_draft else "CREATE",
        actor_user_id=actor_user_id,
        changes={
            "invoice_number": invoice.invoice_number,
            "status": invoice.status.value,
            "total_amount": str(invoice.total_amount),
            "subscription_id": str(subscription.id),
        },
    )
    await db.commit()
    await db.refresh(invoice, ["customer_account", "lines"])
    return invoice


async def recheck_preview_item(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> BillingRunItem:
    """
    Re-evaluate a flagged or pending billing run item against current state.
    Clears warnings if underlying plan/customer issues have been resolved.
    """
    item = (await db.execute(
        select(BillingRunItem).where(BillingRunItem.id == item_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Billing run item not found.")
    if item.status not in (BillingRunItemStatus.FLAGGED, BillingRunItemStatus.FAILED):
        raise HTTPException(status_code=409, detail="Only flagged or failed items can be retried.")

    query = (
        select(Subscription)
        .where(Subscription.id == item.subscription_id)
        .options(*_subscription_options())
    )
    subscription = (await db.execute(query)).scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found.")

    tax_map, default_tax_rule, rules, counts = await _load_pricing_rules(db)
    charge = calculate_subscription_charge(
        subscription,
        tax_map=tax_map,
        default_tax_rule=default_tax_rule,
        discount_rules=rules,
        redemption_counts=counts,
        as_of=item.billing_period_start,
    )
    if subscription.customer_account and not subscription.customer_account.tax_id and tax_map:
        charge.warnings.append("Customer tax ID is missing.")

    item.expected_subtotal = charge.subtotal
    item.expected_tax_amount = charge.tax
    item.expected_discount_amount = charge.discount
    item.expected_total_amount = charge.total
    item.warnings = charge.warnings
    item.status = BillingRunItemStatus.FLAGGED if charge.warnings else BillingRunItemStatus.PENDING
    if not charge.warnings and item.skip_reason:
        item.skip_reason = None

    await record_audit_event(
        db,
        entity_type="billing_run_item",
        entity_id=item.id,
        action="RECHECK",
        actor_user_id=actor_user_id,
        changes={
            "status": item.status.value,
            "warnings_count": len(item.warnings),
            "expected_total_amount": str(item.expected_total_amount),
        },
    )
    await db.commit()
    await db.refresh(item)
    return item
