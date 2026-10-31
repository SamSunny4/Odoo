import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient

from tests.conftest import auth_cookies
from app.models.catalog import ProductType
from app.models.plan import BillingCadence


@pytest.mark.asyncio
async def test_quotation_template_crud(client: AsyncClient, seed_users):
    staff = seed_users["staff"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    staff_cookies = auth_cookies(staff)

    # 1. Create Quotation Template with default lines
    create_payload = {
        "name": "Standard Onboarding Package",
        "validity_days": 45,
        "default_plan_id": str(plan.id),
        "default_lines": [
            {
                "product_id": str(product.id),
                "quantity": 2,
            }
        ],
    }
    res = await client.post("/api/v1/quotation-templates", json=create_payload, cookies=staff_cookies)
    assert res.status_code == 201
    tpl_data = res.json()
    template_id = tpl_data["id"]
    assert tpl_data["name"] == "Standard Onboarding Package"
    assert tpl_data["validity_days"] == 45
    assert tpl_data["default_plan_name"] == plan.name
    assert len(tpl_data["default_lines"]) == 1
    assert tpl_data["default_lines"][0]["product_id"] == str(product.id)
    assert tpl_data["default_lines"][0]["quantity"] == 2

    # 2. List templates
    res = await client.get("/api/v1/quotation-templates", cookies=staff_cookies)
    assert res.status_code == 200
    templates = res.json()
    assert any(t["id"] == template_id for t in templates)

    # 3. Get template by ID
    res = await client.get(f"/api/v1/quotation-templates/{template_id}", cookies=staff_cookies)
    assert res.status_code == 200
    assert res.json()["name"] == "Standard Onboarding Package"

    # 4. Update template
    res = await client.put(
        f"/api/v1/quotation-templates/{template_id}",
        json={"name": "Enterprise Onboarding Package", "validity_days": 60},
        cookies=staff_cookies,
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Enterprise Onboarding Package"
    assert res.json()["validity_days"] == 60

    # 5. Delete template
    res = await client.delete(f"/api/v1/quotation-templates/{template_id}", cookies=staff_cookies)
    assert res.status_code == 200
    assert "deleted successfully" in res.json()["message"]


@pytest.mark.asyncio
async def test_create_quote_from_template_and_unique_numbering(client: AsyncClient, seed_users):
    staff = seed_users["staff"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    staff_cookies = auth_cookies(staff)

    # 1. Create Template with 15 validity days
    tpl_res = await client.post(
        "/api/v1/quotation-templates",
        json={
            "name": "Fast Track Promo",
            "validity_days": 15,
            "default_plan_id": str(plan.id),
            "default_lines": [
                {"product_id": str(product.id), "quantity": 3}
            ],
        },
        cookies=staff_cookies,
    )
    assert tpl_res.status_code == 201
    tpl_id = tpl_res.json()["id"]

    # 2. Create Quote referencing template_id without explicit lines or expiry
    today = date.today()
    quote_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "template_id": tpl_id,
            "status": "quotation",
        },
        cookies=staff_cookies,
    )
    assert quote_res.status_code == 201
    quote = quote_res.json()
    assert quote["subscription_number"].startswith(f"SUB-{today.year}-")
    assert quote["status"] == "quotation"
    assert quote["customer_name"] == customer_account.company_name
    assert quote["plan_name"] == plan.name
    # Expiry date auto-calculated from template validity (15 days)
    expected_expiry = (today + timedelta(days=15)).isoformat()
    assert quote["expiry_date"] == expected_expiry
    # Lines auto-populated from template
    assert len(quote["lines"]) == 1
    assert quote["lines"][0]["quantity"] == 3


@pytest.mark.asyncio
async def test_subscription_lifecycle_and_traceable_audit_history(client: AsyncClient, seed_users):
    """
    Test full state transition pipeline:
    DRAFT -> QUOTATION -> CONFIRMED -> ACTIVE -> CLOSED
    and verify traceable audit history.
    """
    staff = seed_users["staff"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    staff_cookies = auth_cookies(staff)

    # 1. Create in DRAFT status
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": str(plan.id),
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=staff_cookies,
    )
    assert sub_res.status_code == 201
    sub = sub_res.json()
    sub_id = sub["id"]
    assert sub["status"] == "draft"

    # 2. Staff issues Quotation
    res_quote = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "issue_quote", "reason": "Sent formal quotation to client"},
        cookies=staff_cookies,
    )
    assert res_quote.status_code == 200
    assert res_quote.json()["status"] == "quotation"
    assert res_quote.json()["expiry_date"] is not None

    # 3. Customer accepts quote -> CONFIRMED
    res_conf = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "confirm", "reason": "Signed purchase agreement received"},
        cookies=staff_cookies,
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "confirmed"

    # 4. Activate subscription -> ACTIVE (calculates initial next_billing_date)
    res_act = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "activate"},
        cookies=staff_cookies,
    )
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "active"
    assert res_act.json()["next_billing_date"] == str(date.today())

    # 5. Check Subscription Details & Traceable History
    res_detail = await client.get(f"/api/v1/subscriptions/{sub_id}", cookies=staff_cookies)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["customer_name"] == customer_account.company_name
    assert detail["plan_name"] == plan.name
    assert len(detail["lines"]) == 1

    # Verify audit history items
    history = detail["audit_history"]
    actions_logged = [h["action"] for h in history]
    assert "CREATE_SUBSCRIPTION" in actions_logged
    assert "ISSUE_QUOTATION" in actions_logged
    assert "CONFIRM_QUOTATION" in actions_logged
    assert "ACTIVATE_SUBSCRIPTION" in actions_logged

    # Verify actor info is populated
    latest_event = history[0]
    assert latest_event["actor_user_id"] == str(staff.id)
    assert latest_event["actor_email"] == staff.email
    assert latest_event["actor_role"] == "staff"


@pytest.mark.asyncio
async def test_pause_resume_policies(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Create Plan with allow_pause = False
    plan_res = await client.post(
        "/api/v1/plans",
        json={
            "name": "No Pause Monthly",
            "cadence": "monthly",
            "base_price": "500.00",
            "allow_pause": False,
        },
        cookies=admin_cookies,
    )
    assert plan_res.status_code == 201
    no_pause_plan_id = plan_res.json()["id"]

    # 2. Create and activate subscription on this plan
    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": no_pause_plan_id,
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub_id = sub_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 3. Attempt to pause -> 400 Bad Request
    pause_fail = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "pause"},
        cookies=admin_cookies,
    )
    assert pause_fail.status_code == 400
    assert "policy" in pause_fail.json()["detail"].lower()

    # 4. Create Plan with allow_pause = True
    plan_ok_res = await client.post(
        "/api/v1/plans",
        json={
            "name": "Pause Allowed Monthly",
            "cadence": "monthly",
            "base_price": "500.00",
            "allow_pause": True,
        },
        cookies=admin_cookies,
    )
    plan_ok_id = plan_ok_res.json()["id"]

    sub2_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": plan_ok_id,
            "status": "draft",
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub2_id = sub2_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub2_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub2_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 5. Pause succeeds
    pause_ok = await client.post(
        f"/api/v1/subscriptions/{sub2_id}/status",
        json={"action": "pause", "reason": "Customer requested holiday pause"},
        cookies=admin_cookies,
    )
    assert pause_ok.status_code == 200
    assert pause_ok.json()["status"] == "paused"

    # 6. Resume succeeds
    resume_ok = await client.post(
        f"/api/v1/subscriptions/{sub2_id}/status",
        json={"action": "resume"},
        cookies=admin_cookies,
    )
    assert resume_ok.status_code == 200
    assert resume_ok.json()["status"] == "active"


@pytest.mark.asyncio
async def test_renewal_and_early_close_policies(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # 1. Plan with allow_renewal = False and allow_early_close = False
    plan_strict = await client.post(
        "/api/v1/plans",
        json={
            "name": "Strict Locked Plan",
            "cadence": "monthly",
            "base_price": "1000.00",
            "allow_renewal": False,
            "allow_early_close": False,
            "auto_close_on_expiry": True,
        },
        cookies=admin_cookies,
    )
    assert plan_strict.status_code == 201
    strict_plan_id = plan_strict.json()["id"]

    today = date.today()
    future_expiry = today + timedelta(days=60)

    sub_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": strict_plan_id,
            "status": "draft",
            "expiry_date": future_expiry.isoformat(),
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    sub_id = sub_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 2. Renewal rejected
    renew_fail = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "renew"},
        cookies=admin_cookies,
    )
    assert renew_fail.status_code == 400
    assert "renewal" in renew_fail.json()["detail"].lower()

    # 3. Early close rejected before expiry date
    close_fail = await client.post(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"action": "close", "reason": "Customer wants early exit"},
        cookies=admin_cookies,
    )
    assert close_fail.status_code == 400
    assert "early closure" in close_fail.json()["detail"].lower()

    # 4. Plan with allow_renewal = True and allow_early_close = True
    plan_flex = await client.post(
        "/api/v1/plans",
        json={
            "name": "Flexible Plan",
            "cadence": "monthly",
            "base_price": "800.00",
            "allow_renewal": True,
            "allow_early_close": True,
        },
        cookies=admin_cookies,
    )
    flex_plan_id = plan_flex.json()["id"]

    sub_flex_res = await client.post(
        "/api/v1/subscriptions",
        json={
            "customer_account_id": str(customer_account.id),
            "plan_id": flex_plan_id,
            "status": "draft",
            "expiry_date": future_expiry.isoformat(),
            "lines": [{"product_id": str(product.id), "quantity": 1}],
        },
        cookies=admin_cookies,
    )
    flex_sub_id = sub_flex_res.json()["id"]
    await client.post(f"/api/v1/subscriptions/{flex_sub_id}/status", json={"action": "confirm"}, cookies=admin_cookies)
    await client.post(f"/api/v1/subscriptions/{flex_sub_id}/status", json={"action": "activate"}, cookies=admin_cookies)

    # 5. Renewal extends expiry date
    renew_ok = await client.post(
        f"/api/v1/subscriptions/{flex_sub_id}/status",
        json={"action": "renew", "renewal_duration_days": 90},
        cookies=admin_cookies,
    )
    assert renew_ok.status_code == 200
    expected_new_expiry = (future_expiry + timedelta(days=90)).isoformat()
    assert renew_ok.json()["expiry_date"] == expected_new_expiry

    # 6. Early close succeeds
    close_ok = await client.post(
        f"/api/v1/subscriptions/{flex_sub_id}/status",
        json={"action": "close", "reason": "Mutual termination"},
        cookies=admin_cookies,
    )
    assert close_ok.status_code == 200
    assert close_ok.json()["status"] == "closed"
