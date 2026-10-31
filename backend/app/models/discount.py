import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    String, Numeric, Boolean, Integer, Date, DateTime, Enum, ForeignKey,
    CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin, utc_now


class DiscountType(str, enum.Enum):
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class DiscountScope(str, enum.Enum):
    PRODUCT = "product"
    SUBSCRIPTION = "subscription"


class DiscountRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-configured discount rules with criteria, usage limits, and validity."""
    __tablename__ = "discount_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    discount_type: Mapped[DiscountType] = mapped_column(
        Enum(DiscountType, native_enum=False, length=20),
        nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    scope: Mapped[DiscountScope] = mapped_column(
        Enum(DiscountScope, native_enum=False, length=20),
        default=DiscountScope.SUBSCRIPTION,
        nullable=False,
    )
    target_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    min_spend: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_usage_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("value > 0", name="chk_discount_value_positive"),
        CheckConstraint("min_spend >= 0", name="chk_discount_min_spend_non_neg"),
        CheckConstraint("min_quantity >= 0", name="chk_discount_min_quantity_non_neg"),
    )


class DiscountRedemption(Base, UUIDPrimaryKeyMixin):
    """
    Atomic discount redemption records.
    Prevents race conditions by enforcing a unique constraint on (discount_rule_id, invoice_id)
    and counting real rows rather than relying on an incremented integer.
    """
    __tablename__ = "discount_redemptions"

    discount_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discount_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("discount_rule_id", "invoice_id", name="uq_discount_rule_invoice"),
    )

