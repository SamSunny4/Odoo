import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String, Numeric, Integer, Date, Enum, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.customer import CustomerAccount
    from app.models.plan import Plan
    from app.models.catalog import Product, ProductVariant
    from app.models.tax import TaxRule


class SubscriptionStatus(str, enum.Enum):
    DRAFT = "draft"
    QUOTATION = "quotation"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class Subscription(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Core recurring subscription agreement."""
    __tablename__ = "subscriptions"

    subscription_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    customer_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, length=20),
        default=SubscriptionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    billing_anchor_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    __table_args__ = (
        CheckConstraint("billing_anchor_day >= 1 AND billing_anchor_day <= 31", name="chk_sub_anchor_day_range"),
        CheckConstraint("payment_terms_days >= 0", name="chk_sub_payment_terms_non_neg"),
    )

    # Relationships
    customer_account: Mapped["CustomerAccount"] = relationship(
        "CustomerAccount",
        back_populates="subscriptions",
    )
    plan: Mapped["Plan"] = relationship("Plan")
    lines: Mapped[List["SubscriptionLine"]] = relationship(
        "SubscriptionLine",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionLine(Base, UUIDPrimaryKeyMixin):
    """Line item within a subscription representing recurring products or variants."""
    __tablename__ = "subscription_lines"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="chk_sub_line_quantity_pos"),
        CheckConstraint("unit_price >= 0", name="chk_sub_line_unit_price_non_neg"),
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship("Subscription", back_populates="lines")
    product: Mapped["Product"] = relationship("Product")
    variant: Mapped[Optional["ProductVariant"]] = relationship("ProductVariant")
    tax_rule: Mapped[Optional["TaxRule"]] = relationship("TaxRule")

