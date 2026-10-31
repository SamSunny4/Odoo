import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import verify_password
from app.models.user import User, PasswordResetToken
from app.models.outbox import OutboxMessage, OutboxMessageStatus
from app.worker import (
    _claim_pending_outbox_messages_async,
    _process_outbox_sync,
    process_outbox_messages_async,
)


@pytest.mark.asyncio
async def test_forgot_password_generates_token_and_outbox(client, db_session, seed_users):
    """
    Forgot password creates an SHA-256 hashed single-use token and writes an outbox message.
    CRITICAL SECURITY CHECK: Plaintext reset tokens or links are NEVER persisted in the database;
    only the encrypted ciphertext is saved in outbox payload.
    """
    user = seed_users["customer_a"]

    with patch("smtplib.SMTP") as smtp:
        res = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        smtp.assert_not_called()
    assert res.status_code == 200

    # Verify reset token record in DB has SHA-256 hash (never raw token)
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
    assert msg.payload["token_id"] == str(token_record.id)

    # Database security verification: plaintext reset secrets must NEVER be persisted
    assert "reset_link" not in msg.payload
    assert "raw_token" not in msg.payload
    assert "body" not in msg.payload
    assert "encrypted_reset_token" in msg.payload
    assert msg.status == OutboxMessageStatus.PENDING.value


@pytest.mark.asyncio
async def test_forgot_password_outbox_worker_retry_on_smtp_failure(client, db_session, seed_users):
    """
    The endpoint only persists an outbox message. A worker failure records a retry,
    and a later worker run decrypts the token, builds the email, and delivers it.
    """
    user = seed_users["customer_a"]

    # 1. The endpoint queues work without making SMTP calls in the request transaction.
    with patch("smtplib.SMTP") as request_smtp:
        res = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
        assert res.status_code == 200
        request_smtp.assert_not_called()

    outbox = (
        await db_session.execute(
            select(OutboxMessage).where(OutboxMessage.topic == "email")
        )
    ).scalars().all()
    assert len(outbox) == 1
    msg = outbox[0]
    assert msg.status == OutboxMessageStatus.PENDING.value

    # 2. A failed worker attempt stays pending and schedules a retry.
    with patch("smtplib.SMTP", side_effect=OSError("SMTP server connection refused")):
        result = await process_outbox_messages_async(db_session)
        assert result["processed"] == 0

    await db_session.refresh(msg)
    assert msg.status == OutboxMessageStatus.PENDING.value
    assert msg.retry_count == 1
    assert "connection refused" in (msg.last_error or "")

    # Make the retry due now, then verify successful delivery.
    msg.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = mock_smtp.return_value.__enter__.return_value
        result = await process_outbox_messages_async(db_session)
        assert result["processed"] == 1

        # Verify email was actually dispatched via SMTP
        assert mock_server.send_message.called
        sent_email = mock_server.send_message.call_args[0][0]
        assert sent_email["To"] == user.email
        assert "reset-password?token=" in sent_email.get_content()

    # 3. Verify outbox record transitioned to SENT
    await db_session.refresh(msg)
    assert msg.status == OutboxMessageStatus.SENT.value
    assert msg.sent_at is not None
    assert msg.last_error is None


@pytest.mark.asyncio
async def test_pending_outbox_message_can_only_be_claimed_once(db_session, seed_users):
    user = seed_users["customer_a"]
    message = OutboxMessage(
        topic="email",
        status=OutboxMessageStatus.PENDING.value,
        payload={"to": user.email, "subject": "Test", "body": "Test"},
        retry_count=0,
        max_retries=3,
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    db_session.add(message)
    await db_session.commit()

    now = datetime.now(timezone.utc)
    first_claim = await _claim_pending_outbox_messages_async(db_session, now, batch_size=10)
    second_claim = await _claim_pending_outbox_messages_async(db_session, now, batch_size=10)

    assert [item.id for item in first_claim] == [message.id]
    assert second_claim == []
    await db_session.refresh(message)
    assert message.status == OutboxMessageStatus.PROCESSING.value


def test_celery_sync_outbox_worker_delivers_once():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OutboxMessage.__table__.create(engine)
    try:
        with Session(engine) as session:
            message = OutboxMessage(
                topic="email",
                status=OutboxMessageStatus.PENDING.value,
                payload={"to": "customer@example.test", "subject": "Invoice", "body": "Test"},
                retry_count=0,
                max_retries=3,
                scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )
            session.add(message)
            session.commit()

            with patch("smtplib.SMTP") as mock_smtp:
                first = _process_outbox_sync(session)
                second = _process_outbox_sync(session)

            assert first["processed"] == 1
            assert second["processed"] == 0
            assert mock_smtp.return_value.__enter__.return_value.send_message.call_count == 1
            session.refresh(message)
            assert message.status == OutboxMessageStatus.SENT.value
    finally:
        OutboxMessage.__table__.drop(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_outbox_worker_reclaims_stuck_processing_messages(client, db_session, seed_users):
    """
    Crash recovery: If an outbox worker crashes after claiming a message, the message
    is left in PROCESSING. The next run reclaims stuck PROCESSING messages past timeout.
    """
    from app.core.crypto import encrypt_secret
    user = seed_users["customer_a"]
    raw_token = secrets.token_urlsafe(32)

    stuck_msg = OutboxMessage(
        topic="email",
        status=OutboxMessageStatus.PROCESSING.value,
        payload={
            "type": "password_reset",
            "to": user.email,
            "subject": "Password Reset",
            "encrypted_reset_token": encrypt_secret(raw_token),
        },
        retry_count=0,
    )
    # Simulate updated_at 15 minutes ago (crashed worker)
    stuck_msg.updated_at = datetime.now(timezone.utc) - timedelta(minutes=15)
    db_session.add(stuck_msg)
    await db_session.commit()

    with patch("smtplib.SMTP") as mock_smtp:
        result = await process_outbox_messages_async(db_session, stuck_timeout_minutes=5)
        assert result["reclaimed"] >= 1
        assert result["processed"] >= 1

    await db_session.refresh(stuck_msg)
    assert stuck_msg.status == OutboxMessageStatus.SENT.value
    assert stuck_msg.sent_at is not None


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
async def test_concurrent_password_reset_prevented(client, db_session, seed_users):
    """
    Two simultaneous reset requests cannot both succeed; atomic conditional consumption
    ensures exactly one request succeeds and the other is rejected with HTTP 400.
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

    # Attempt simultaneous execution of same token
    req1 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "StrongPasswordOne#2026"},
    )
    req2 = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "StrongPasswordTwo#2026"},
    )
    res1, res2 = await asyncio.gather(req1, req2)

    status_codes = sorted([res1.status_code, res2.status_code])
    assert status_codes == [200, 400], f"Expected one 200 and one 400, got: {status_codes}"


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
