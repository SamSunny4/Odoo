import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.conftest import auth_cookies
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.outbox import OutboxMessage
from app.models.audit import AuditEvent


@pytest.mark.asyncio
async def test_generate_draft_invoice_from_subscription_and_snapshots(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Setup Tax Rule (10%) and Product-scoped Discount ($20 off)
    tax_res = await client.post(
        "/api/v1/tax-rules",
        json={"name": "VAT Standard 10%", "rate_percentage": "10.00"},
        cookies=admin_cookies,
    )
    assert tax_res.status_code == 201
    tax_id = tax_res.json()["id"]

    disc_res = await client.post(
        "/api/v1/discount-rules",
        json={
            "name": "Phase 5 Promo $20",
            "discount_type": "fixed",
            "value": "20.00",
            "scope": "product",
            "target_product_id": str(product.id),
            "min_spend": "50.00",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
        },
        cookies=admin_cookies,
    )
    assert disc_res.status_code == 201

    # 2. Create Active Subscription
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 2, "tax_rule_id": tax_id}],
        },
        cookies=admin_cookies,
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    act_res = await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)
    assert act_res.status_code == 200

    # 3. Generate Draft Invoice directly from subscription
    gen_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "subscription_id": sub_id,
            "as_draft": True,
        },
        cookies=admin_cookies,
    )
    assert gen_res.status_code == 201
    inv_data = gen_res.json()
    assert inv_data["status"] == "draft"
    assert inv_data["customer_name"] == customer_account.company_name
    assert inv_data["customer_snapshot"]["company_name"] == customer_account.company_name
    assert inv_data["billing_address_snapshot"]["city"] == customer_account.billing_city

    # Check line item snapshots
    assert len(inv_data["lines"]) >= 2  # Plan line + Product line
    product_line = next(l for l in inv_data["lines"] if l["product_name_snapshot"] == product.name)
    assert product_line["quantity"] == 2
    assert Decimal(product_line["discount_amount"]) == Decimal("20.00")
    assert Decimal(product_line["tax_amount"]) > Decimal("0.00")
    assert Decimal(inv_data["total_amount"]) > Decimal("0.00")


@pytest.mark.asyncio
async def test_invoice_confirm_cancel_with_reason_and_send(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Create and activate subscription
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

    # 2. Generate Draft Invoice
    draft_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    assert draft_res.status_code == 201
    inv_id = draft_res.json()["id"]

    # 3. Confirm Invoice
    confirm_res = await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "confirmed"

    # 4. Send Invoice
    send_res = await client.post(f"/api/v1/invoices/{inv_id}/send", cookies=admin_cookies)
    assert send_res.status_code == 200
    assert send_res.json()["send_status"] == "sent"
    assert send_res.json()["sent_at"] is not None

    # 5. Cancel Invoice with audit reason
    cancel_res = await client.post(
        f"/api/v1/invoices/{inv_id}/cancel",
        json={"reason": "Customer agreed to upgrade to annual enterprise plan instead."},
        cookies=admin_cookies,
    )
    assert cancel_res.status_code == 200
    cancelled_inv = cancel_res.json()
    assert cancelled_inv["status"] == "cancelled"
    assert "upgrade to annual enterprise" in cancelled_inv["cancellation_reason"]

    # Verify audit history
    detail_res = await client.get(f"/api/v1/invoices/{inv_id}", cookies=admin_cookies)
    assert detail_res.status_code == 200
    actions = [evt["action"] for evt in detail_res.json()["audit_history"]]
    assert "CREATE_DRAFT" in actions
    assert "CONFIRM" in actions
    assert "SEND" in actions
    assert "CANCEL" in actions


@pytest.mark.asyncio
async def test_print_pdf_invoice_endpoint(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

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

    draft_res = await client.post(
        "/api/v1/invoices/generate",
        json={"subscription_id": sub_id, "as_draft": True},
        cookies=admin_cookies,
    )
    inv = draft_res.json()
    inv_id = inv["id"]

    pdf_res = await client.get(f"/api/v1/invoices/{inv_id}/pdf", cookies=admin_cookies)
    assert pdf_res.status_code == 200
    assert "text/html" in pdf_res.headers.get("content-type", "")
    content = pdf_res.text
    assert inv["invoice_number"] in content
    assert customer_account.company_name in content
    assert "Brightloop Software" in content


@pytest.mark.asyncio
async def test_idempotent_invoice_generation_prevents_duplicate_billing(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

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

    # 1. Generate First Invoice for this period
    first_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "subscription_id": sub_id,
            "as_draft": False,
            "billing_period_start": "2026-05-01",
            "billing_period_end": "2026-05-31",
        },
        cookies=admin_cookies,
    )
    assert first_res.status_code == 201

    # 2. Re-running the same billing period MUST be rejected with 409
    dup_res = await client.post(
        "/api/v1/invoices/generate",
        json={
            "subscription_id": sub_id,
            "as_draft": False,
            "billing_period_start": "2026-05-01",
            "billing_period_end": "2026-05-31",
        },
        cookies=admin_cookies,
    )
    assert dup_res.status_code == 409
    assert "already been generated" in dup_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_control_tower_preview_commit_and_exception_queue(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Create clean subscription
    sub1_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub1_id = sub1_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub1_id}/status", json={"action": "issue_quote"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub1_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub1_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 2. Run Control Tower Preview with batch limit
    preview_res = await client.post("/api/v1/control-tower/preview?batch_size=50", cookies=admin_cookies)
    assert preview_res.status_code == 200
    preview = preview_res.json()
    run_id = preview["billing_run_id"]
    assert preview["total_subscriptions"] >= 1

    # 3. Historical Runs List
    runs_res = await client.get("/api/v1/control-tower/runs", cookies=admin_cookies)
    assert runs_res.status_code == 200
    assert any(r["id"] == run_id for r in runs_res.json())

    # 4. Run Details
    run_detail_res = await client.get(f"/api/v1/control-tower/runs/{run_id}", cookies=admin_cookies)
    assert run_detail_res.status_code == 200
    items = run_detail_res.json()["items"]
    assert len(items) >= 1

    # 5. Skip control
    item_to_skip = items[0]
    skip_res = await client.post(
        f"/api/v1/control-tower/items/{item_to_skip['id']}/skip",
        json={"reason": "Manual hold requested by account executive."},
        cookies=admin_cookies,
    )
    assert skip_res.status_code == 200
    assert skip_res.json()["status"] == "skipped"

    # 6. Retry control
    retry_res = await client.post(
        f"/api/v1/control-tower/items/{item_to_skip['id']}/retry",
        cookies=admin_cookies,
    )
    assert retry_res.status_code == 200
    assert "status" in retry_res.json()


@pytest.mark.asyncio
async def test_automated_recurring_billing_run(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    admin_cookies = auth_cookies(admin)

    auto_bill_res = await client.post("/api/v1/control-tower/auto-bill", cookies=admin_cookies)
    assert auto_bill_res.status_code == 200
    data = auto_bill_res.json()
    assert data["status"] == "completed"
    assert "invoices_created" in data
    assert "emails_queued" in data

