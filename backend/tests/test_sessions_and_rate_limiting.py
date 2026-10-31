import pytest
from app.core.config import settings


@pytest.mark.asyncio
async def test_session_cookie_lifecycle(client, seed_users):
    """
    Sign-in sets a secure HTTP-only session cookie.
    Client can authenticate via cookie without Authorization header.
    Logout clears the session cookie.
    """
    # 1. Sign in
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@brightloop.local", "password": "Admin@12345!"},
    )
    assert login_res.status_code == 200
    assert settings.SESSION_COOKIE_NAME in client.cookies

    # Check Set-Cookie headers
    set_cookie_header = login_res.headers.get("set-cookie", "")
    assert settings.SESSION_COOKIE_NAME in set_cookie_header
    assert "httponly" in set_cookie_header.lower()

    # 2. Access /auth/me with cookie
    me_res = await client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["user"]["email"] == "admin@brightloop.local"

    # 3. Log out
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # 4. Next request to protected route without valid session must fail
    me_after_logout = await client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limiting(client, seed_users):
    """Rapid successive login attempts trigger HTTP 429 Too Many Requests."""
    for attempt in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@brightloop.local", "password": "WrongPassword@999!"},
        )
        assert res.status_code == 401, f"Attempt {attempt+1} should fail authentication with 401"

    # 6th attempt exceeds limit
    blocked_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@brightloop.local", "password": "WrongPassword@999!"},
    )
    assert blocked_res.status_code == 429
    assert "Retry-After" in blocked_res.headers
    assert "rate limit exceeded" in blocked_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forgot_password_rate_limiting(client):
    """Rapid forgot-password requests trigger HTTP 429 Too Many Requests."""
    for attempt in range(5):
        res = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "someone@brightloop.local"},
        )
        assert res.status_code == 200

    # 6th attempt exceeds limit
    blocked_res = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "someone@brightloop.local"},
    )
    assert blocked_res.status_code == 429
    assert "Retry-After" in blocked_res.headers
    assert "rate limit exceeded" in blocked_res.json()["detail"].lower()

