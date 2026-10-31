from __future__ import annotations
import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator, ConfigDict
from app.models.user import UserRole
from app.core.security import validate_password_strength

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(?:\.[a-zA-Z0-9\-]+)+$")


def validate_email_address(v: str) -> str:
    cleaned = v.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError("Invalid email address format.")
    return cleaned


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class AuthSuccessResponse(BaseModel):
    message: str = "Authenticated successfully."
    user: UserResponse


class Token(BaseModel):
    message: str = "Authenticated successfully."
    token_type: str = "cookie"
    access_token: Optional[str] = None
    user: Optional[UserResponse] = None


class TokenPayload(BaseModel):
    sub: str
    email: str
    role: str
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_address(v)


class SignupRequest(BaseModel):
    """
    Public registration request.
    Strictly forces Customer role; creates both User and CustomerAccount with owner membership.
    """
    email: str
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

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_address(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_address(v)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v


class CreateStaffRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: UserRole = UserRole.STAFF
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return validate_email_address(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        validate_password_strength(v)
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: UserRole) -> UserRole:
        if v not in (UserRole.ADMIN, UserRole.STAFF):
            raise ValueError("Role must be either 'admin' or 'staff'.")
        return v


class UpdateStaffRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[UserRole]) -> Optional[UserRole]:
        if v is not None and v not in (UserRole.ADMIN, UserRole.STAFF):
            raise ValueError("Role must be either 'admin' or 'staff'.")
        return v


class CustomerAccountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str
    billing_email: str
    currency: str


class AuthMeResponse(BaseModel):
    user: UserResponse
    customer_account: Optional[CustomerAccountSummary] = None
