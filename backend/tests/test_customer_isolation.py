import pytest
from datetime import date, timedelta
from decimal import Decimal
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_customer_data_isolation(client, db_session, seed_users):
    """
    Customer isolation check:
    Customer A and Customer B can strictly only view records associated with their own account.
    """
    account_a = seed_users["account_a"]
    account_b = seed_users["account_b"]
    plan = seed_users["plan"]
    customer_a = seed_users["customer_a"]
    customer_b = seed_users["customer_b"]

    # 1. Create a Subscription and Invoice for Customer A
    sub_a = Subscription(
        subscription_number="SUB-CUST-A-001",
        customer_account_id=account_a.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2026, 1, 1),
        billing_anchor_day=1,
        payment_terms_days=15,
    )
    db_session.add(sub_a)
    await db_session.flush()

    inv_a = Invoice(
        invoice_number="INV-CUST-A-001",
        subscription_id=sub_a.id,
        idempotency_key="idemp_inv_cust_a_001",
        customer_snapshot={"company_name": "Acme Corp"},
        billing_address_snapshot={"city": "Austin"},
        customer_account_id=account_a.id,
        currency="USD",
        status=InvoiceStatus.CONFIRMED,
        billing_period_start=date(2026, 1, 1),
        billing_period_end=date(2026, 1, 31),
        subtotal=Decimal("200.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("200.00"),
        paid_amount=Decimal("0.00"),
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 16),
        send_status=SendStatus.SENT,
    )
    db_session.add(inv_a)

    # 2. Create a Subscription and Invoice for Customer B
    sub_b = Subscription(
        subscription_number="SUB-CUST-B-002",
        customer_account_id=account_b.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2026, 2, 1),
        billing_anchor_day=1,
        payment_terms_days=30,
    )
    db_session.add(sub_b)
    await db_session.flush()

    inv_b = Invoice(
        invoice_number="INV-CUST-B-002",
        subscription_id=sub_b.id,
        idempotency_key="idemp_inv_cust_b_002",
        customer_snapshot={"company_name": "Beta Industries"},
        billing_address_snapshot={"city": "Seattle"},
        customer_account_id=account_b.id,
        currency="USD",
        status=InvoiceStatus.PAID,
        billing_period_start=date(2026, 2, 1),
        billing_period_end=date(2026, 2, 28),
        subtotal=Decimal("300.00"),
        tax_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("300.00"),
        paid_amount=Decimal("300.00"),
        issue_date=date(2026, 2, 1),
        due_date=date(2026, 3, 3),
        send_status=SendStatus.SENT,
    )
    db_session.add(inv_b)
    await db_session.commit()

    # 3. Test Customer A sees ONLY Customer A's data
    client.cookies.clear()
    client.cookies.update(auth_cookies(customer_a))

    res_subs_a = await client.get("/api/v1/portal/subscriptions")
    assert res_subs_a.status_code == 200
    subs_a_data = res_subs_a.json()
    assert len(subs_a_data) == 1
    assert subs_a_data[0]["subscription_number"] == "SUB-CUST-A-001"

    res_invs_a = await client.get("/api/v1/portal/invoices")
    assert res_invs_a.status_code == 200
    invs_a_data = res_invs_a.json()
    assert len(invs_a_data) == 1
    assert invs_a_data[0]["invoice_number"] == "INV-CUST-A-001"
    own_pdf = await client.get(f"/api/v1/portal/invoices/{inv_a.id}/pdf")
    foreign_pdf = await client.get(f"/api/v1/portal/invoices/{inv_b.id}/pdf")
    assert own_pdf.status_code == 200
    assert own_pdf.headers.get("content-type") == "application/pdf"
    assert foreign_pdf.status_code == 404

    # 4. Test Customer B sees ONLY Customer B's data
    client.cookies.clear()
    client.cookies.update(auth_cookies(customer_b))

    res_subs_b = await client.get("/api/v1/portal/subscriptions")
    assert res_subs_b.status_code == 200
    subs_b_data = res_subs_b.json()
    assert len(subs_b_data) == 1
    assert subs_b_data[0]["subscription_number"] == "SUB-CUST-B-002"

    res_invs_b = await client.get("/api/v1/portal/invoices")
    assert res_invs_b.status_code == 200
    invs_b_data = res_invs_b.json()
    assert len(invs_b_data) == 1
    assert invs_b_data[0]["invoice_number"] == "INV-CUST-B-002"


@pytest.mark.asyncio
async def test_portal_derives_account_strictly_from_session(client, seed_users):
    """Passing malicious account_id parameter in query does not alter session derivation."""
    customer_a = seed_users["customer_a"]
    account_b = seed_users["account_b"]

    client.cookies.update(auth_cookies(customer_a))

    # Even if attacker attempts query tampering
    res_subs = await client.get(f"/api/v1/portal/subscriptions?customer_account_id={account_b.id}")
    assert res_subs.status_code == 200
    # Customer A still only gets their own context (or empty), never Account B
    for sub in res_subs.json():
        assert sub["customer_account_id"] == str(seed_users["account_a"].id)


@pytest.mark.asyncio
async def test_portal_subscription_action_obeys_account_scope_and_plan_policy(client, db_session, seed_users):
    account_a = seed_users["account_a"]
    customer_a = seed_users["customer_a"]
    customer_b = seed_users["customer_b"]
    plan = seed_users["plan"]
    plan.allow_early_close = False
    subscription = Subscription(
        subscription_number="SUB-PORTAL-ACTION-001",
        customer_account_id=account_a.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date.today(),
        expiry_date=date.today() + timedelta(days=60),
        billing_anchor_day=1,
        payment_terms_days=15,
    )
    db_session.add(subscription)
    await db_session.commit()

    client.cookies.update(auth_cookies(customer_a))
    own_action = await client.post(
        f"/api/v1/portal/subscriptions/{subscription.id}/actions",
        json={"action": "cancel", "reason": "Do not renew"},
    )
    assert own_action.status_code == 200
    assert own_action.json()["status"] == "active"
    assert own_action.json()["cancel_at_period_end"] is True

    client.cookies.clear()
    client.cookies.update(auth_cookies(customer_b))
    foreign_action = await client.post(
        f"/api/v1/portal/subscriptions/{subscription.id}/actions",
        json={"action": "pause"},
    )
    assert foreign_action.status_code == 404

