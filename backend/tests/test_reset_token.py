import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.models.user import User, PasswordResetToken
from app.models.outbox import OutboxMessage


@pytest.mark.asyncio
async def test_forgot_password_generates_token_and_outbox(client, db_session, seed_users):
    """
    Forgot password creates an SHA-256 hashed single-use token and writes an outbox message
    using the configured settings.FRONTEND_URL.
    """
    user = seed_users["customer_a"]

    res = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert res.status_code == 200

    # Verify reset token record in DB
    tokens = (
        await db_session.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
    ).scalars().all()
    assert len(tokens) == 1
    token_record = tokens[0]
    assert token_record.is_used is False
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)

    # Verify OutboxMessage
    outbox = (
        await db_session.execute(
            select(OutboxMessage).where(OutboxMessage.topic == "email")
        )
    ).scalars().all()
    assert len(outbox) == 1
    msg = outbox[0]
    assert msg.payload["type"] == "password_reset"
    assert msg.payload["to"] == user.email
    expected_frontend = settings.FRONTEND_URL.rstrip('/')
    assert msg.payload["reset_link"].startswith(f"{expected_frontend}/reset-password?token=")


@pytest.mark.asyncio
async def test_successful_password_reset_and_reuse_prevention(client, db_session, seed_users):
    """
    Resetting password succeeds with valid token, updates password hash,
    and marks token used so it CANNOT be reused.
    """
    user = seed_users["customer_a"]
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    token_rec = PasswordResetToken(
        user_id=user.id,
        token=hashed_token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_used=False,
    )
    db_session.add(token_rec)
    await db_session.commit()

    # 1. Successful reset
    new_password = "BrandNewSecurePassword@2026#"
    res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
    )
    assert res.status_code == 200
    assert "successfully reset" in res.json()["message"].lower()

    # Verify user can sign in with new password
    await db_session.refresh(user)
    assert verify_password(new_password, user.hashed_password)

    # 2. Token reuse attempt must be rejected
    res_reuse = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPassword@999!"},
    )
    assert res_reuse.status_code == 400
    assert "invalid or expired" in res_reuse.json()["detail"].lower()


@pytest.mark.asyncio
async def test_expired_reset_token_rejected(client, db_session, seed_users):
    """Expired reset token is rejected with HTTP 400 Bad Request."""
    user = seed_users["customer_a"]
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    # Set expiration in past
    token_rec = PasswordResetToken(
        user_id=user.id,
        token=hashed_token,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        is_used=False,
    )
    db_session.add(token_rec)
    await db_session.commit()

    res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewStrongPass#2026!"},
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_reset_token_rejected(client):
    """Fabricated or non-existent token is rejected with HTTP 400 Bad Request."""
    res = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": "completely_fake_token_value", "new_password": "NewStrongPass#2026!"},
    )
    assert res.status_code == 400
    assert "invalid or expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_password_complexity_enforced_on_reset(client, db_session, seed_users):
    """Resetting password enforces Brightloop password rules (>8 chars, upper, lower, special)."""
    user = seed_users["customer_a"]
    raw_token = secrets.token_urlsafe(32)
    hashed_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    token_rec = PasswordResetToken(
        user_id=user.id,
        token=hashed_token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        is_used=False,
    )
    db_session.add(token_rec)
    await db_session.commit()

    weak_passwords = [
        "short@1",          # <= 8 chars
        "alllowercase@123", # Missing uppercase
        "ALLUPPERCASE@123", # Missing lowercase
        "NoSpecialChar123", # Missing special char
    ]

    for weak_pass in weak_passwords:
        res = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": weak_pass},
        )
        assert res.status_code in (400, 422), f"Weak password '{weak_pass}' should be rejected"

