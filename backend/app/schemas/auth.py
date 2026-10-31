import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator
from app.models.user import UserRole
from app.core.security import validate_password_strength


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    email: str
    role: str
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    """
    Public registration request.
    Strictly forces Customer role; creates both User and CustomerAccount with owner membership.
    """
    email: EmailStr
    password: str
    full_name: str
    company_name: str
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    billing_address_line1: str
    billing_address_line2: Optional[str] = None
    billing_city: str
    billing_state: Optional[str] = None
    billing_postal_code: str
    billing_country: str = "US"  # ISO 3166-1 alpha-2

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerAccountSummary(BaseModel):
    id: uuid.UUID
    company_name: str
    billing_email: str
    currency: str

    class Config:
        from_attributes = True


class AuthMeResponse(BaseModel):
    user: UserResponse
    customer_account: Optional[CustomerAccountSummary] = None

