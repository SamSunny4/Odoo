import pytest
import uuid
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(client):
    """Unauthenticated calls to protected endpoints return HTTP 401 Unauthorized."""
    endpoints = [
        ("GET", "/api/v1/auth/me"),
        ("GET", "/api/v1/admin/staff"),
        ("GET", "/api/v1/subscriptions"),
        ("GET", "/api/v1/invoices"),
        ("GET", "/api/v1/portal/subscriptions"),
    ]
    for method, path in endpoints:
        res = await client.request(method, path)
        assert res.status_code == 401, f"{method} {path} should return 401, got {res.status_code}"


@pytest.mark.asyncio
async def test_customer_cannot_access_staff_or_admin_endpoints(client, seed_users):
    """Customer role is forbidden from operational and administrative endpoints."""
    customer = seed_users["customer_a"]
    client.cookies.update(auth_cookies(customer))

    restricted_endpoints = [
        ("GET", "/api/v1/admin/staff"),
        ("POST", "/api/v1/admin/staff", {"email": "test@brightloop.local", "password": "Pass@12345!", "full_name": "Test", "role": "staff"}),
        ("GET", "/api/v1/subscriptions"),
        ("GET", "/api/v1/invoices"),
        ("POST", "/api/v1/payments", {"invoice_id": str(uuid.uuid4()), "amount": 10.0, "payment_method": "credit_card", "payment_date": "2026-10-31"}),
        ("POST", "/api/v1/control-tower/preview"),
    ]

    for item in restricted_endpoints:
        method = item[0]
        path = item[1]
        json_body = item[2] if len(item) > 2 else None
        res = await client.request(method, path, json=json_body)
        assert res.status_code == 403, f"Customer should be 403 Forbidden for {method} {path}, got {res.status_code}"


@pytest.mark.asyncio
async def test_staff_cannot_access_admin_only_endpoints(client, seed_users):
    """Operations staff is forbidden from admin-only endpoints."""
    staff = seed_users["staff"]
    client.cookies.update(auth_cookies(staff))

    # 1. Staff directory & creation
    res_list = await client.get("/api/v1/admin/staff")
    assert res_list.status_code == 403

    res_create = await client.post(
        "/api/v1/admin/staff",
        json={"email": "newstaff@brightloop.local", "password": "Pass@12345!", "full_name": "New Staff", "role": "staff"},
    )
    assert res_create.status_code == 403

    # 2. Commit billing batch (admin only)
    res_commit = await client.post(
        f"/api/v1/control-tower/runs/{uuid.uuid4()}/commit",
        json={"approved_item_ids": []},
    )
    assert res_commit.status_code == 403


@pytest.mark.asyncio
async def test_product_cost_price_role_boundaries(client, seed_users):
    """
    Catalog cost_price visibility:
    - Admin CAN see cost_price.
    - Staff CANNOT see cost_price (cost_price is null).
    - Customer CANNOT see cost_price (cost_price is null).
    """
    admin = seed_users["admin"]
    staff = seed_users["staff"]
    customer = seed_users["customer_a"]

    # Admin check
    client.cookies.clear()
    client.cookies.update(auth_cookies(admin))
    res_admin = await client.get("/api/v1/products")
    assert res_admin.status_code == 200
    products_admin = res_admin.json()
    assert len(products_admin) > 0
    assert products_admin[0]["cost_price"] is not None

    # Staff check
    client.cookies.clear()
    client.cookies.update(auth_cookies(staff))
    res_staff = await client.get("/api/v1/products")
    assert res_staff.status_code == 200
    products_staff = res_staff.json()
    assert len(products_staff) > 0
    assert products_staff[0]["cost_price"] is None

    # Customer check
    client.cookies.clear()
    client.cookies.update(auth_cookies(customer))
    res_customer = await client.get("/api/v1/products")
    assert res_customer.status_code == 200
    products_customer = res_customer.json()
    assert len(products_customer) > 0
    assert products_customer[0]["cost_price"] is None

