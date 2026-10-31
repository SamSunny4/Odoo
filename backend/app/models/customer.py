import enum
import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import String, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.subscription import Subscription
    from app.models.invoice import Invoice


class CustomerMembershipRole(str, enum.Enum):
    OWNER = "owner"
    BILLING_ADMIN = "billing_admin"
    VIEWER = "viewer"


class CustomerAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Business entity / Customer company holding subscriptions and invoices."""
    __tablename__ = "customer_accounts"

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    tax_id: Mapped[str] = mapped_column(String(50), nullable=True)

    # Billing Address
    billing_address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_address_line2: Mapped[str] = mapped_column(String(255), nullable=True)
    billing_city: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_state: Mapped[str] = mapped_column(String(100), nullable=True)
    billing_postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    billing_country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # Relationships
    memberships: Mapped[List["CustomerAccountMembership"]] = relationship(
        "CustomerAccountMembership",
        back_populates="customer_account",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="customer_account",
    )
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="customer_account",
    )


class CustomerAccountMembership(Base, UUIDPrimaryKeyMixin):
    """Associates users with customer accounts for multi-user access per customer."""
    __tablename__ = "customer_account_memberships"

    customer_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_role: Mapped[CustomerMembershipRole] = mapped_column(
        Enum(CustomerMembershipRole, native_enum=False, length=20),
        default=CustomerMembershipRole.OWNER,
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("customer_account_id", "user_id", name="uq_customer_account_user"),
    )

    # Relationships
    customer_account: Mapped["CustomerAccount"] = relationship(
        "CustomerAccount",
        back_populates="memberships",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memberships",
    )

