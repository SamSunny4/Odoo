import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.rate_limit import (
    rate_limit_login,
    rate_limit_forgot_password,
    rate_limit_reset_password,
)
from app.services.audit import record_audit_event
from app.services.outbox import create_outbox_message
from app.models.user import User, UserRole, PasswordResetToken
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    Token,
    AuthMeResponse,
    UserResponse,
    CustomerAccountSummary,
)
from app.api.v1.deps import get_current_active_user

router = APIRouter()


def set_session_cookie(response: Response, token: str) -> None:
    """Sets secure HTTP-only session cookie for web clients."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def delete_session_cookie(response: Response) -> None:
    """Clears HTTP-only session cookie."""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def register_customer(
    payload: SignupRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Public customer registration.
    - Strictly forces role = 'customer' (never allows self-assigning staff/admin).
    - Creates customer user account and company record with owner membership.
    - Emits audit log record and establishes HTTP-only session cookie.
    """
    normalized_email = payload.email.lower().strip()

    # Check for existing email (case-insensitive normalized)
    existing_user_query = select(User).where(User.email == normalized_email)
    existing_user = (await db.execute(existing_user_query)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # 1. Create User (Enforce CUSTOMER role)
    new_user = User(
        email=normalized_email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # 2. Create Customer Account (Company)
    new_account = CustomerAccount(
        company_name=payload.company_name,
        billing_email=normalized_email,
        phone=payload.phone,
        tax_id=payload.tax_id,
        billing_address_line1=payload.billing_address_line1,
        billing_address_line2=payload.billing_address_line2,
        billing_city=payload.billing_city,
        billing_state=payload.billing_state,
        billing_postal_code=payload.billing_postal_code,
        billing_country=payload.billing_country,
    )
    db.add(new_account)
    await db.flush()

    # 3. Create Owner Membership
    membership = CustomerAccountMembership(
        customer_account_id=new_account.id,
        user_id=new_user.id,
        membership_role=CustomerMembershipRole.OWNER,
    )
    db.add(membership)

    # 4. Record Audit Event
    await record_audit_event(
        db,
        entity_type="user",
        entity_id=new_user.id,
        action="SIGNUP",
        actor_user_id=new_user.id,
        changes={"email": new_user.email, "role": new_user.role.value, "company_name": payload.company_name},
    )

    await db.commit()

    # Generate token and set HTTP-only cookie
    token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email, "role": new_user.role.value}
    )
    set_session_cookie(response, token)
    return Token(access_token=token, token_type="bearer")


@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit_login)], tags=["Auth"])
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate user with email and password.
    Returns signed JWT access token and sets secure HTTP-only session cookie.
    Enforces sliding-window rate limiting.
    """
    normalized_email = payload.email.lower().strip()
    query = select(User).where(User.email == normalized_email)
    user = (await db.execute(query)).scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Contact your administrator.",
        )

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    set_session_cookie(response, token)

    await record_audit_event(
        db,
        entity_type="user",
        entity_id=user.id,
        action="LOGIN",
        actor_user_id=user.id,
    )
    await db.commit()

    return Token(access_token=token, token_type="bearer")


@router.post("/logout", tags=["Auth"])
async def logout(response: Response):
    """
    Sign out user by invalidating and clearing HTTP-only session cookie.
    """
    delete_session_cookie(response)
    return {"message": "Session terminated successfully."}


@router.get("/me", response_model=AuthMeResponse, tags=["Auth"])
async def get_current_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns current authenticated profile and customer account if customer.
    """
    account_summary = None
    if current_user.role == UserRole.CUSTOMER and current_user.memberships:
        membership = current_user.memberships[0]
        acc_query = select(CustomerAccount).where(CustomerAccount.id == membership.customer_account_id)
        account = (await db.execute(acc_query)).scalar_one_or_none()
        if account:
            account_summary = CustomerAccountSummary.model_validate(account)

    return AuthMeResponse(
        user=UserResponse.model_validate(current_user),
        customer_account=account_summary,
    )


@router.post("/forgot-password", dependencies=[Depends(rate_limit_forgot_password)], tags=["Auth"])
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate single-use password reset link.
    Stores token hashed with SHA-256 and persists reset email in outbox.
    Uses configurable settings.FRONTEND_URL for the reset link.
    Enforces sliding-window rate limiting.
    """
    normalized_email = payload.email.lower().strip()
    query = select(User).where(User.email == normalized_email)
    user = (await db.execute(query)).scalar_one_or_none()

    # Always return generic message to avoid email enumeration
    if user and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token=hashed_token,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(reset_token)

        frontend_base = settings.FRONTEND_URL.rstrip('/')
        reset_link = f"{frontend_base}/reset-password?token={raw_token}"
        email_body = (
            f"Hello {user.full_name},\n\n"
            f"A password reset request was initiated for your Brightloop account.\n\n"
            f"Use the following secure link within 1 hour to reset your password:\n"
            f"{reset_link}\n\n"
            f"If you did not request this, please disregard this email.\n\n"
            f"Brightloop Security Team"
        )

        # Durable outbox message
        await create_outbox_message(
            db,
            topic="email",
            payload={
                "type": "password_reset",
                "to": user.email,
                "subject": "Password Reset Request — Brightloop Software",
                "body": email_body,
                "reset_link": reset_link,
                "expires_at": expires_at.isoformat(),
            },
        )

        await record_audit_event(
            db,
            entity_type="user",
            entity_id=user.id,
            action="FORGOT_PASSWORD_REQUESTED",
            actor_user_id=user.id,
        )

        await db.commit()

        # Send password reset email via configured SMTP (Mailpit in dev)
        msg = EmailMessage()
        msg["Subject"] = "Password Reset Request — Brightloop Software"
        msg["From"] = settings.SMTP_FROM
        msg["To"] = user.email
        msg.set_content(email_body)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                server.send_message(msg)
        except Exception as exc:
            # Fallback for offline dev
            print(f"[Auth] SMTP dispatch failed ({exc}). Password reset queued for {user.email}")

    return {
        "message": "If an account with that email exists, password reset instructions have been dispatched."
    }


@router.post("/reset-password", dependencies=[Depends(rate_limit_reset_password)], tags=["Auth"])
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Complete password reset with single-use expirable token.
    Validates token against stored SHA-256 hash and enforces password complexity policy.
    Enforces sliding-window rate limiting.
    """
    hashed_token = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()

    query = select(PasswordResetToken).where(
        PasswordResetToken.token == hashed_token,
        PasswordResetToken.is_used == False,  # noqa: E712
    )
    token_record = (await db.execute(query)).scalar_one_or_none()

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    # Check expiration
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new one.",
        )

    # Retrieve user
    user = (await db.execute(select(User).where(User.id == token_record.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    # Update password and invalidate token
    user.hashed_password = get_password_hash(payload.new_password)
    token_record.is_used = True

    await record_audit_event(
        db,
        entity_type="user",
        entity_id=user.id,
        action="PASSWORD_RESET",
        actor_user_id=user.id,
    )

    await db.commit()

    return {"message": "Password successfully reset. You may now sign in with your new credentials."}
