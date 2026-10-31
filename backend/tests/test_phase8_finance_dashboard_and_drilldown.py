import uuid
from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentMethod
from app.core.clock import organization_today
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_dashboard_summary_metrics_and_rule_definitions(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    admin_cookies = auth_cookies(admin)

    # 1. Default (this_month)
    res = await client.get("/api/v1/reports/summary", cookies=admin_cookies)
    assert res.status_code == 200
    data = res.json()

    assert data["currency"] == "USD"
    assert data["period"] == "this_month"
    assert data["period_start"] is not None
    assert data["period_end"] is not None
    assert "monthly_recurring_revenue" in data
    assert "invoiced_revenue" in data
    assert "cash_collected" in data
    assert "outstanding_balance" in data
    assert "overdue_balance" in data
    assert "active_subscription_count" in data
    assert "overdue_invoice_count" in data

    # Verify metric definitions exist for accounting clarity
    defs = data.get("metric_definitions", {})
    assert "monthly_recurring_revenue" in defs
    assert "invoiced_revenue" in defs
    assert "cash_collected" in defs
    assert "outstanding_balance" in defs

    # 2. Period switching
    for period in ["last_month", "this_quarter", "this_year", "all_time"]:
        p_res = await client.get(f"/api/v1/reports/summary?period={period}", cookies=admin_cookies)
        assert p_res.status_code == 200
        p_data = p_res.json()
        assert p_data["period"] == period
        assert p_data["period_start"] is not None
        assert p_data["period_end"] is not None


@pytest.mark.asyncio
async def test_drill_down_invoiced_revenue(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Create active subscription & confirmed invoice
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
    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # Drill-down by invoiced metric
    dd_res = await client.get("/api/v1/reports/drill-down?metric=invoiced&period=this_month", cookies=admin_cookies)
    assert dd_res.status_code == 200
    dd_data = dd_res.json()
    assert dd_data["metric"] == "invoiced"
    assert dd_data["total_items"] >= 1
    assert any(item["id"] == inv_id for item in dd_data["items"])

    matched = next(item for item in dd_data["items"] if item["id"] == inv_id)
    assert matched["entity_type"] == "invoice"
    assert matched["customer_name"] == customer_account.company_name
    assert Decimal(str(matched["amount"])) > Decimal("0.00")
    invoiced_summary = await client.get("/api/v1/reports/summary?period=this_month", cookies=admin_cookies)
    assert Decimal(str(dd_data["total_amount"])) == Decimal(str(invoiced_summary.json()["invoiced_revenue"]))

    mrr_report = await client.get("/api/v1/reports/drill-down?metric=subscriptions&period=this_month", cookies=admin_cookies)
    assert mrr_report.status_code == 200
    assert Decimal(str(mrr_report.json()["total_amount"])) == Decimal(
        str(invoiced_summary.json()["monthly_recurring_revenue"])
    )


@pytest.mark.asyncio
async def test_drill_down_cash_collected_vs_invoiced(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Setup subscription and invoice
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
    await client.post(f"/api/v1/invoices/{inv_id}/confirm", cookies=admin_cookies)

    # Record Payment
    pay_res = await client.post(
        "/api/v1/payments",
        json={
            "invoice_id": inv_id,
            "amount": 75.00,
            "payment_method": "bank_transfer",
            "payment_date": organization_today().isoformat(),
            "reference_note": "Audit Verification Remittance",
        },
        cookies=admin_cookies,
    )
    assert pay_res.status_code == 201
    pay_id = pay_res.json()["id"]

    # Partial refund must reduce cash collected by exactly the refunded amount.
    refund_res = await client.post(
        f"/api/v1/payments/{pay_id}/reverse",
        json={"amount": 25.00, "reason": "Refund part of remittance"},
        cookies=admin_cookies,
    )
    assert refund_res.status_code == 200
    assert refund_res.json()["is_reversed"] is False

    # Drill down and summary must reconcile to the same net cash amount.
    dd_res = await client.get("/api/v1/reports/drill-down?metric=collected&period=this_month", cookies=admin_cookies)
    assert dd_res.status_code == 200
    dd_data = dd_res.json()
    assert dd_data["metric"] == "collected"
    assert any(item["id"] == pay_id for item in dd_data["items"])

    matched_pay = next(item for item in dd_data["items"] if item["id"] == pay_id)
    assert matched_pay["entity_type"] == "payment"
    assert matched_pay["metric_category"] == "Cash Collections"
    assert Decimal(str(matched_pay["amount"])) == Decimal("50.00")
    assert Decimal(str(dd_data["total_amount"])) == Decimal("50.00")
    summary_res = await client.get("/api/v1/reports/summary?period=this_month", cookies=admin_cookies)
    assert summary_res.status_code == 200
    assert Decimal(str(summary_res.json()["cash_collected"])) == Decimal("50.00")
    outstanding_res = await client.get("/api/v1/reports/drill-down?metric=outstanding", cookies=admin_cookies)
    assert outstanding_res.status_code == 200
    assert Decimal(str(outstanding_res.json()["total_amount"])) == Decimal(
        str(summary_res.json()["outstanding_balance"])
    )


@pytest.mark.asyncio
async def test_drill_down_filtering_and_pagination(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    admin_cookies = auth_cookies(admin)

    # Filter by specific customer account
    cust_res = await client.get(
        f"/api/v1/reports/drill-down?metric=all&customer_account_id={customer_account.id}",
        cookies=admin_cookies,
    )
    assert cust_res.status_code == 200
    cust_data = cust_res.json()
    assert "items" in cust_data
    assert "total_pages" in cust_data
    assert cust_data["page"] == 1

    # Filter by plan
    plan_res = await client.get(
        f"/api/v1/reports/drill-down?metric=subscriptions&plan_id={plan.id}",
        cookies=admin_cookies,
    )
    assert plan_res.status_code == 200
    assert plan_res.json()["metric"] == "subscriptions"

    partial_period = await client.get(
        "/api/v1/reports/summary?period=custom&start_date=2026-10-01",
        cookies=admin_cookies,
    )
    assert partial_period.status_code == 422

    reversed_period = await client.get(
        "/api/v1/reports/summary?period=custom&start_date=2026-10-31&end_date=2026-10-01",
        cookies=admin_cookies,
    )
    assert reversed_period.status_code == 422


@pytest.mark.asyncio
async def test_finance_csv_export_endpoint(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    admin_cookies = auth_cookies(admin)

    # Download CSV export
    export_res = await client.get("/api/v1/reports/export?metric=invoiced&period=this_month", cookies=admin_cookies)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers.get("content-type", "")
    assert "attachment" in export_res.headers.get("content-disposition", "")
    assert ".csv" in export_res.headers.get("content-disposition", "")

    csv_text = export_res.text
    assert "Reference Number" in csv_text
    assert "Customer Name" in csv_text
    assert "Amount" in csv_text
    assert "Outstanding Balance" in csv_text


@pytest.mark.asyncio
async def test_control_tower_csv_export_endpoint(client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    customer_account = seed_users["account_a"]
    plan = seed_users["plan"]
    product = seed_users["product"]
    admin_cookies = auth_cookies(admin)

    # Setup subscription
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

    # Run Control Tower preview
    preview_res = await client.post("/api/v1/control-tower/preview?batch_size=50", cookies=admin_cookies)
    assert preview_res.status_code == 200
    run_id = preview_res.json()["billing_run_id"]

    # Export preview run as CSV
    export_res = await client.get(f"/api/v1/control-tower/runs/{run_id}/export", cookies=admin_cookies)
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers.get("content-type", "")
    assert f"billing_run_{run_id}" in export_res.headers.get("content-disposition", "")

    csv_text = export_res.text
    assert "Subscription #" in csv_text
    assert "Expected Total" in csv_text
    assert "Variance Amount" in csv_text
    assert "Warnings" in csv_text

