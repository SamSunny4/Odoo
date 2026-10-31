import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.customer import CustomerAccountMembership


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """System user representing Admin, Staff, or Customer identity."""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.CUSTOMER,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    memberships: Mapped[List["CustomerAccountMembership"]] = relationship(
        "CustomerAccountMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class PasswordResetToken(Base, UUIDPrimaryKeyMixin):
    """Single-use, time-limited password reset token sent only to registered email."""
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


