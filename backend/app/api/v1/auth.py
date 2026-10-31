from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserRole
from app.models.customer import CustomerAccount, CustomerAccountMembership, CustomerMembershipRole
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    Token,
    AuthMeResponse,
    UserResponse,
    CustomerAccountSummary,
)
from app.api.v1.deps import get_current_active_user

router = APIRouter()


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def register_customer(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Public customer registration.
    - Strictly forces role = 'customer' (never allows self-assigning staff/admin).
    - Creates customer user account and company record with owner membership.
    """
    normalized_email = payload.email.lower().strip()

    # Check for existing email
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
    await db.commit()

    # Generate token
    token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email, "role": new_user.role.value}
    )
    return Token(access_token=token, token_type="bearer")


@router.post("/login", response_model=Token, tags=["Auth"])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user with email and password.
    Returns signed JWT access token.
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
    return Token(access_token=token, token_type="bearer")


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

