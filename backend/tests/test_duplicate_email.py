import pytest
from app.models.user import UserRole
from tests.conftest import auth_cookies


@pytest.mark.asyncio
async def test_signup_rejects_duplicate_email(client, seed_users):
    """Registering a new account with an existing email returns HTTP 409 Conflict."""
    payload = {
        "email": "customer.a@acme.com",  # Already seeded
        "password": "ValidPassword@123!",
        "full_name": "Duplicate User",
        "company_name": "Duplicate Inc",
        "billing_address_line1": "123 Main St",
        "billing_city": "Austin",
        "billing_postal_code": "78701",
        "billing_country": "US",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409
    data = response.json()
    assert "already exists" in data["detail"].lower()


@pytest.mark.asyncio
async def test_signup_rejects_case_insensitive_duplicate_email(client, seed_users):
    """Email normalization ensures uppercase/mixed-case variants are rejected."""
    payload = {
        "email": "  CUSTOMER.A@ACME.COM  ",  # Mixed case and surrounding whitespace
        "password": "ValidPassword@123!",
        "full_name": "Duplicate User Upper",
        "company_name": "Duplicate Inc Upper",
        "billing_address_line1": "123 Main St",
        "billing_city": "Austin",
        "billing_postal_code": "78701",
        "billing_country": "US",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_staff_creation_rejects_duplicate_email(client, seed_users):
    """Admin endpoint to create staff rejects duplicate email with HTTP 409 Conflict."""
    admin = seed_users["admin"]
    client.cookies.update(auth_cookies(admin))

    payload = {
        "email": "staff@brightloop.local",  # Already exists
        "password": "StaffPassword@123!",
        "full_name": "Another Staff",
        "role": "staff",
    }
    response = await client.post("/api/v1/admin/staff", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_staff_creation_case_insensitive_duplicate(client, seed_users):
    """Admin staff creation enforces case-insensitive normalized email uniqueness."""
    admin = seed_users["admin"]
    client.cookies.update(auth_cookies(admin))

    payload = {
        "email": "STAFF@brightloop.LOCAL",
        "password": "StaffPassword@123!",
        "full_name": "Another Staff",
        "role": "staff",
    }
    response = await client.post("/api/v1/admin/staff", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()

