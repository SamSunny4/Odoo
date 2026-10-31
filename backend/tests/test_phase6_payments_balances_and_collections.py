import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod, PaymentReversal
from app.models.outbox import OutboxMessage
from app.models.audit import AuditEvent
from app.core.clock import organization_today
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_record_multiple_payments_and_balance_tracking(client: AsyncClient, seed_users, db_session):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Create and activate a subscription
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 2. Generate and confirm invoice
    inv_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    assert inv_res.status_code == 201
    inv_id = inv_res.json()["id"]
    total_amount = Decimal(str(inv_res.json()["total_amount"]))
    assert total_amount > Decimal("0.00")

    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # 3. Record First Partial Payment (e.g. 40% of total)
    partial_amount = (total_amount * Decimal("0.4")).quantize(Decimal("0.01"))
    pay1_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": float(partial_amount),
            "payment_method": "bank_transfer",
            "payment_date": date.today().isoformat(),
            "reference_note": "Partial Wire Remittance #1",
        },
        cookies=admin_cookies,
    )
    assert pay1_res.status_code == 201
    pay1_data = pay1_res.json()
    assert pay1_data["is_reversed"] is False
    assert Decimal(str(pay1_data["amount"])) == partial_amount

    # 4. Check Invoice State: status must remain CONFIRMED, paid_amount updated, balance reduced
    detail_res = await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)
    inv_detail = detail_res.json()
    assert inv_detail["status"] == "confirmed"
    assert Decimal(str(inv_detail["paid_amount"])) == partial_amount
    expected_balance = total_amount - partial_amount
    assert Decimal(str(inv_detail["outstanding_balance"])) == expected_balance

    # 5. Check invoice filters: partially_paid filter must return this invoice
    filter_res = await client.get("/api/v1/invoices?status=partially_paid", cookies=admin_cookies)
    assert filter_res.status_code == 200
    partially_paid_ids = [inv["id"] for inv in filter_res.json()]
    assert inv_id in partially_paid_ids

    # 6. Record Second Payment settling remaining balance
    pay2_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": float(expected_balance),
            "payment_method": "credit_card",
            "payment_date": date.today().isoformat(),
            "reference_note": "Final Settling Payment #2",
        },
        cookies=admin_cookies,
    )
    assert pay2_res.status_code == 201

    # 7. Check Invoice State: status must now transition to PAID and balance to 0
    detail_res2 = await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)
    inv_detail2 = detail_res2.json()
    assert inv_detail2["status"] == "paid"
    assert Decimal(str(inv_detail2["paid_amount"])) == total_amount
    assert Decimal(str(inv_detail2["outstanding_balance"])) == Decimal("0.00")
    assert len(inv_detail2["payments"]) == 2

    # Verify receipt email was queued into outbox
    outbox_stmt = select(OutboxMessage).where(OutboxMessage.topic == "email")
    messages = (await db_session.execute(outbox_stmt)).scalars().all()
    receipts = [m for m in messages if m.payload.get("type") == "payment_receipt"]
    assert len(receipts) >= 1


@pytest.mark.asyncio
async def test_payment_validation_and_overpayment_prevention(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Create subscription and draft invoice
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub_id = sub_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    inv_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    inv_id = inv_res.json()["id"]
    total = Decimal(str(inv_res.json()["total_amount"]))

    # A. Attempt payment on draft invoice -> should fail with 400
    draft_pay_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": 50.00,
            "payment_method": "cash",
            "payment_date": date.today().isoformat(),
        },
        cookies=admin_cookies,
    )
    assert draft_pay_res.status_code == 400

    # Confirm invoice
    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # B. Attempt payment of zero or negative -> should fail with 400 or 422
    neg_pay_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": -10.00,
            "payment_method": "cash",
            "payment_date": date.today().isoformat(),
        },
        cookies=admin_cookies,
    )
    assert neg_pay_res.status_code in (400, 422)

    precision_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": 10.001,
            "payment_method": "cash",
            "payment_date": date.today().isoformat(),
        },
        cookies=admin_cookies,
    )
    assert precision_res.status_code == 422

    # C. Attempt overpayment (exceeding balance) -> should fail with 400
    excess_amount = float(total + Decimal("500.00"))
    overpay_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": excess_amount,
            "payment_method": "bank_transfer",
            "payment_date": date.today().isoformat(),
        },
        cookies=admin_cookies,
    )
    assert overpay_res.status_code == 400
    assert "cannot exceed remaining balance" in overpay_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_payment_reversal_and_refund_workflow(client: AsyncClient, seed_users, db_session):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Setup subscription and confirmed invoice
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub_id = sub_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    inv_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    inv_id = inv_res.json()["id"]
    total = float(inv_res.json()["total_amount"])
    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # Record full payment settling the invoice
    pay_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": total,
            "payment_method": "credit_card",
            "payment_date": date.today().isoformat(),
            "reference_note": "Initial Full Payment",
        },
        cookies=admin_cookies,
    )
    assert pay_res.status_code == 201
    payment_id = pay_res.json()["id"]

    # Verify invoice is PAID
    inv_after_pay = (await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)).json()
    assert inv_after_pay["status"] == "paid"

    # A partial refund restores only that amount and remains reversible.
    rev_reason = "Customer chargeback claim settled via support ticket #7821"
    rev_res = await client.post(
        f"/api/v1/payments/{payment_id}/reverse",
        json={"reason": rev_reason, "amount": total / 2},
        cookies=admin_cookies,
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["is_reversed"] is False
    assert rev_data["reversal"] is not None
    assert rev_data["reversal"]["reason"] == rev_reason
    assert Decimal(str(rev_data["reversal"]["reversal_amount"])) == Decimal(str(total / 2))
    assert len(rev_data["reversals"]) == 1

    # Verify a partial refund leaves the invoice open with the remaining paid amount.
    inv_after_rev = (await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)).json()
    assert inv_after_rev["status"] == "confirmed"
    assert Decimal(str(inv_after_rev["paid_amount"])) == Decimal(str(total / 2))
    assert Decimal(str(inv_after_rev["outstanding_balance"])) == Decimal(str(total / 2))

    # Refund the remaining amount as a second immutable record.
    second_rev = await client.post(
        f"/api/v1/payments/{payment_id}/reverse",
        json={"reason": "Remaining balance refunded"},
        cookies=admin_cookies,
    )
    assert second_rev.status_code == 200
    assert second_rev.json()["is_reversed"] is True
    assert len(second_rev.json()["reversals"]) == 2
    inv_after_full_rev = (await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)).json()
    assert Decimal(str(inv_after_full_rev["paid_amount"])) == Decimal("0.00")
    assert Decimal(str(inv_after_full_rev["outstanding_balance"])) == Decimal(str(total))

    # Re-reversing the same payment must fail
    dup_rev_res = await client.post(
        f"/api/v1/payments/{payment_id}/reverse",
        json={"reason": "Attempting second reversal"},
        cookies=admin_cookies,
    )
    assert dup_rev_res.status_code == 400
    assert "fully reversed" in dup_rev_res.json()["detail"].lower()

    # Verify audit event was logged
    audit_stmt = select(AuditEvent).where(
        AuditEvent.entity_type == "payment",
        AuditEvent.action == "REVERSE_PAYMENT",
        AuditEvent.entity_id == uuid.UUID(payment_id),
    )
    audit_ev = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit_ev is not None


@pytest.mark.asyncio
async def test_payment_provider_adapter_and_webhooks(client: AsyncClient):
    # Webhook callback simulation on provider adapter
    webhook_res = await client.post(
        "/api/v1/payments/webhooks/manual",
        json={
            "event_type": "charge.succeeded",
            "provider": "manual",
            "external_id": "ch_mock_98234123",
            "amount": 125.50,
            "currency": "USD",
            "metadata": {"source": "external_gateway"},
        },
    )
    assert webhook_res.status_code == 200
    wh_data = webhook_res.json()
    assert wh_data["status"] == "acknowledged"
    assert wh_data["provider"] == "manual"
    assert wh_data["result"]["success"] is True
    assert wh_data["result"]["status"] == "settled"


@pytest.mark.asyncio
async def test_invoice_status_and_balance_filters(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Create sub & invoice
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub_id = sub_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    inv_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    inv_id = inv_res.json()["id"]

    # Filter by draft
    drafts = (await client.get("/api/v1/invoices?status=draft", cookies=admin_cookies)).json()
    assert any(i["id"] == inv_id for i in drafts)

    # Confirm
    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # Filter by confirmed
    confirmed = (await client.get("/api/v1/invoices?status=confirmed", cookies=admin_cookies)).json()
    assert any(i["id"] == inv_id for i in confirmed)

    # Filter by outstanding
    outstanding = (await client.get("/api/v1/invoices?status=outstanding", cookies=admin_cookies)).json()
    assert any(i["id"] == inv_id for i in outstanding)


@pytest.mark.asyncio
async def test_collection_queue_aging_and_reminders(client: AsyncClient, seed_users, db_session):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    today = organization_today()

    # Create overdue confirmed invoice directly
    past_due = today - timedelta(days=45)
    overdue_inv = Invoice(
        invoice_number=f"INV-TEST-{uuid.uuid4().hex[:6].upper()}",
        subscription_id=uuid.uuid4(),
        customer_account_id=customer_account.id,
        currency="USD",
        status=InvoiceStatus.CONFIRMED,
        billing_period_start=past_due - timedelta(days=30),
        billing_period_end=past_due,
        subtotal=Decimal("350.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("350.00"),
        paid_amount=Decimal("50.00"),  # $300 balance due
        issue_date=past_due - timedelta(days=15),
        due_date=past_due,
        customer_snapshot={
            "company_name": customer_account.company_name,
            "billing_email": customer_account.billing_email,
        },
        billing_address_snapshot={"address": "123 Overdue Way"},
    )
    db_session.add(overdue_inv)
    await db_session.commit()
    await db_session.refresh(overdue_inv)

    # 1. Query Collection Queue
    queue_res = await client.get("/api/v1/payments/collection-queue", cookies=admin_cookies)
    assert queue_res.status_code == 200
    queue = queue_res.json()

    assert queue["total_overdue_invoices"] >= 1
    assert Decimal(str(queue["total_overdue_balance"])) >= Decimal("300.00")

    # Item must be in 31-60 days aging bucket
    target_item = next((it for it in queue["items"] if it["invoice_id"] == str(overdue_inv.id)), None)
    assert target_item is not None
    assert target_item["days_overdue"] == 45
    assert target_item["aging_bucket"] == "31-60 days"
    assert Decimal(str(target_item["balance_due"])) == Decimal("300.00")

    # 2. Filter collection queue by aging bucket
    bucket_res = await client.get("/api/v1/payments/collection-queue?aging_bucket=31-60", cookies=admin_cookies)
    assert bucket_res.status_code == 200
    filtered_queue = bucket_res.json()
    assert any(it["invoice_id"] == str(overdue_inv.id) for it in filtered_queue["items"])
    assert filtered_queue["total_overdue_invoices"] == len(filtered_queue["items"])
    assert Decimal(str(filtered_queue["total_overdue_balance"])) == sum(
        (Decimal(str(it["balance_due"])) for it in filtered_queue["items"]),
        Decimal("0.00"),
    )

    # 3. Dispatch Overdue Reminder via outbox
    remind_res = await client.post(
        f"/api/v1/payments/collection-queue/{overdue_inv.id}/remind",
        json={"custom_message": "Immediate payment required before service suspension."},
        cookies=admin_cookies,
    )
    assert remind_res.status_code == 200
    remind_data = remind_res.json()
    assert remind_data["status"] == "queued"

    # Verify audit event and outbox message
    outbox_stmt = select(OutboxMessage).where(OutboxMessage.dedupe_key == remind_data["dedupe_key"])
    msg = (await db_session.execute(outbox_stmt)).scalar_one_or_none()
    assert msg is not None
    assert msg.payload["type"] == "overdue_reminder"
    assert "Immediate payment required" in msg.payload["body"]

    # Manual and scheduled reminders share the same window key, so retries don't duplicate mail.
    duplicate_reminder = await client.post(
        f"/api/v1/payments/collection-queue/{overdue_inv.id}/remind",
        json={"custom_message": "This duplicate must not be sent."},
        cookies=admin_cookies,
    )
    assert duplicate_reminder.status_code == 200
    assert duplicate_reminder.json()["dedupe_key"] == remind_data["dedupe_key"]
    assert "already" in duplicate_reminder.json()["message"].lower()

