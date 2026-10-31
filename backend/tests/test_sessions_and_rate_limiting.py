import asyncio
import pytest
from app.core.config import settings


@pytest.mark.asyncio
async def test_session_cookie_lifecycle(client, seed_users):
    """
    Sign-in sets a secure HTTP-only session cookie.
    Client can authenticate via cookie without Authorization header.
    Does NOT leak access_token in the JSON response body.
    Logout clears the session cookie.
    """
    # 1. Sign in
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@brightloop.local", "password": "Brightloop@12345!"},
    )
    assert login_res.status_code == 200
    assert settings.SESSION_COOKIE_NAME in client.cookies

    # Verify no JWT token in body
    login_body = login_res.json()
    assert "access_token" not in login_body

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
async def test_logout_revokes_jwt_server_side(client, seed_users):
    """
    Server-side JWT revocation:
    When a user signs out, their JWT token is added to the revocation blacklist.
    A copied cookie or Bearer token is rejected by the server even if sent directly before natural expiry.
    """
    # 1. Sign in
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@brightloop.local", "password": "Brightloop@12345!"},
    )
    assert login_res.status_code == 200
    copied_cookie_token = client.cookies[settings.SESSION_COOKIE_NAME]

    # Verify the copied token works initially
    me_res_1 = await client.get("/api/v1/auth/me")
    assert me_res_1.status_code == 200

    # 2. Logout on this client (revokes token server-side)
    logout_res = await client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200

    # 3. Simulate an attacker or another client presenting the copied cookie
    client.cookies.set(settings.SESSION_COOKIE_NAME, copied_cookie_token)
    rejected_res = await client.get("/api/v1/auth/me")
    assert rejected_res.status_code == 401

    # Also test presenting via Authorization header
    client.cookies.clear()
    rejected_header_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {copied_cookie_token}"},
    )
    assert rejected_header_res.status_code == 401


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
async def test_atomic_rate_limiting_concurrent_requests(client, seed_users):
    """
    Simultaneous concurrent requests cannot bypass the rate limiter.
    Out of 8 simultaneous requests against a limit of 5, exactly 5 must pass and 3 must be blocked with HTTP 429.
    """
    tasks = [
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@brightloop.local", "password": "WrongPassword@999!"},
        )
        for _ in range(8)
    ]
    results = await asyncio.gather(*tasks)

    status_counts = {}
    for r in results:
        status_counts[r.status_code] = status_counts.get(r.status_code, 0) + 1

    # Exactly 5 should be 401 (processed authentication) and 3 should be 429 (blocked by rate limiter)
    assert status_counts.get(401) == 5, f"Expected 5 requests to be processed, got {status_counts}"
    assert status_counts.get(429) == 3, f"Expected 3 requests to be rate-limited with 429, got {status_counts}"


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


@pytest.mark.asyncio
async def test_spoofed_forwarded_for_header_does_not_bypass_rate_limit(client, seed_users):
    """
    When TRUST_PROXY_HEADERS is False, clients cannot bypass rate limiting
    by alternating spoofed X-Forwarded-For headers.
    """
    for attempt in range(5):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@brightloop.local", "password": "WrongPassword@999!"},
            headers={"X-Forwarded-For": f"198.51.100.{attempt+1}"},
        )
        assert res.status_code == 401

    # 6th attempt with another spoofed IP must still be blocked by real client host
    blocked_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@brightloop.local", "password": "WrongPassword@999!"},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert blocked_res.status_code == 429
    assert "rate limit exceeded" in blocked_res.json()["detail"].lower()
