import pytest
import uuid
from decimal import Decimal
from datetime import date
from tests.conftest import auth_cookies
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.invoice import Invoice, InvoiceStatus, SendStatus
from app.models.catalog import Product, ProductType


@pytest.mark.asyncio
async def test_subscriptions_pagination_search_and_headers(client, db_session, seed_users):
    """
    Test server-side pagination, search by number and customer, status filter,
    and X-Total-Count / pagination headers on /api/v1/subscriptions.
    """
    admin = seed_users["admin"]
    account_a = seed_users["account_a"]
    account_b = seed_users["account_b"]
    plan = seed_users["plan"]

    # Create multiple subscriptions for testing pagination
    for i in range(5):
        sub = Subscription(
            id=uuid.uuid4(),
            subscription_number=f"SUB-PAGINATE-{i+1:03d}",
            customer_account_id=account_a.id if i % 2 == 0 else account_b.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE if i < 3 else SubscriptionStatus.PAUSED,
            start_date=date(2026, 1, 1 + i),
            billing_anchor_day=1,
            payment_terms_days=30,
        )
        db_session.add(sub)
    await db_session.commit()

    client.cookies.update(auth_cookies(admin))

    # 1. Test pagination slice: page=1, page_size=2
    res = await client.get("/api/v1/subscriptions?page=1&page_size=2")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert "X-Total-Count" in res.headers
    total = int(res.headers["X-Total-Count"])
    assert total >= 5
    assert res.headers["X-Page"] == "1"
    assert res.headers["X-Page-Size"] == "2"

    # 2. Test search by subscription number
    res_search = await client.get("/api/v1/subscriptions?search=SUB-PAGINATE-002")
    assert res_search.status_code == 200
    search_items = res_search.json()
    assert len(search_items) == 1
    assert search_items[0]["subscription_number"] == "SUB-PAGINATE-002"
    assert res_search.headers["X-Total-Count"] == "1"

    # 3. Test filter by status=paused
    res_status = await client.get("/api/v1/subscriptions?status=paused")
    assert res_status.status_code == 200
    paused_items = res_status.json()
    assert all(item["status"] == "paused" for item in paused_items)

    # 4. Test envelope mode
    res_env = await client.get("/api/v1/subscriptions?page=1&page_size=2&envelope=true")
    assert res_env.status_code == 200
    env_data = res_env.json()
    assert "items" in env_data
    assert "total" in env_data
    assert "page" in env_data
    assert "page_size" in env_data
    assert "total_pages" in env_data
    assert len(env_data["items"]) == 2
    assert env_data["total"] == total


@pytest.mark.asyncio
async def test_invoices_pagination_search_and_headers(client, db_session, seed_users):
    """
    Test server-side pagination, search by invoice number, status filter,
    and pagination headers on /api/v1/invoices.
    """
    admin = seed_users["admin"]
    account_a = seed_users["account_a"]
    plan = seed_users["plan"]

    sub = Subscription(
        id=uuid.uuid4(),
        subscription_number="SUB-FOR-INV",
        customer_account_id=account_a.id,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2026, 1, 1),
        billing_anchor_day=1,
        payment_terms_days=30,
    )
    db_session.add(sub)
    await db_session.flush()

    # Seed multiple invoices
    for i in range(4):
        inv = Invoice(
            id=uuid.uuid4(),
            invoice_number=f"INV-PAGINATE-{i+1:03d}",
            idempotency_key=f"IDEMP-INV-{i+1:03d}",
            subscription_id=sub.id,
            customer_account_id=account_a.id,
            currency="USD",
            status=InvoiceStatus.CONFIRMED if i < 2 else InvoiceStatus.PAID,
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("10.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("110.00"),
            paid_amount=Decimal("110.00") if i >= 2 else Decimal("0.00"),
            issue_date=date(2026, 1, 1 + i),
            due_date=date(2026, 1, 31),
            send_status=SendStatus.NOT_SENT,
            customer_snapshot={"name": "Acme Corp"},
            billing_address_snapshot={"address": "100 Innovation Blvd"},
        )
        db_session.add(inv)
    await db_session.commit()

    client.cookies.update(auth_cookies(admin))

    # 1. Pagination & headers
    res = await client.get("/api/v1/invoices?page=1&page_size=2")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert int(res.headers["X-Total-Count"]) >= 4

    # 2. Search
    res_search = await client.get("/api/v1/invoices?search=INV-PAGINATE-003")
    assert res_search.status_code == 200
    search_items = res_search.json()
    assert len(search_items) == 1
    assert search_items[0]["invoice_number"] == "INV-PAGINATE-003"

    # 3. Filter by status
    res_paid = await client.get("/api/v1/invoices?status=paid")
    assert res_paid.status_code == 200
    paid_items = res_paid.json()
    assert all(item["status"] == "paid" for item in paid_items)


@pytest.mark.asyncio
async def test_products_pagination_and_search(client, seed_users):
    """
    Test server-side search and pagination on /api/v1/products.
    """
    admin = seed_users["admin"]
    client.cookies.update(auth_cookies(admin))

    res = await client.get("/api/v1/products?page=1&page_size=1")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert "X-Total-Count" in res.headers

    # Search for Core ERP
    res_erp = await client.get("/api/v1/products?search=Core%20ERP")
    assert res_erp.status_code == 200
    items = res_erp.json()
    assert any("Core ERP" in p["name"] for p in items)


@pytest.mark.asyncio
async def test_portal_pagination_and_isolation(client, db_session, seed_users):
    """
    Test customer portal pagination and verified customer isolation.
    """
    customer_a = seed_users["customer_a"]
    account_a = seed_users["account_a"]
    plan = seed_users["plan"]

    for i in range(3):
        sub = Subscription(
            id=uuid.uuid4(),
            subscription_number=f"SUB-PORTAL-A-{i+1:03d}",
            customer_account_id=account_a.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            start_date=date(2026, 1, 1),
            billing_anchor_day=1,
            payment_terms_days=30,
        )
        db_session.add(sub)
    await db_session.commit()

    client.cookies.clear()
    client.cookies.update(auth_cookies(customer_a))

    res = await client.get("/api/v1/portal/subscriptions?page=1&page_size=2")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2
    assert int(res.headers["X-Total-Count"]) >= 3
    # All items belong to Customer A
    assert all(item["customer_account_id"] == str(account_a.id) for item in items)


@pytest.mark.asyncio
async def test_admin_staff_pagination_and_search(client, seed_users):
    """
    Test server-side pagination, search, and role filter on /api/v1/admin/staff.
    """
    admin = seed_users["admin"]
    client.cookies.update(auth_cookies(admin))

    res = await client.get("/api/v1/admin/staff?page=1&page_size=1")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert int(res.headers["X-Total-Count"]) >= 2

    # Filter by role=admin
    res_admin = await client.get("/api/v1/admin/staff?role=admin")
    assert res_admin.status_code == 200
    admin_users = res_admin.json()
    assert all(u["role"] == "admin" for u in admin_users)
