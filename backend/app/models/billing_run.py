import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String, Numeric, Integer, Date, DateTime, Enum, ForeignKey, Text, JSON,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class BillingRunStatus(str, enum.Enum):
    PREVIEW = "preview"
    COMMITTED = "committed"
    FAILED = "failed"


class BillingRunItemStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    FLAGGED = "flagged"
    SKIPPED = "skipped"
    INVOICED = "invoiced"
    FAILED = "failed"


class BillingRun(Base, UUIDPrimaryKeyMixin):
    """
    Billing Control Tower Run record.
    Tracks batch preview and atomic execution of recurring billing.
    """
    __tablename__ = "billing_runs"

    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[BillingRunStatus] = mapped_column(
        Enum(BillingRunStatus, native_enum=False, length=20),
        default=BillingRunStatus.PREVIEW,
        nullable=False,
        index=True,
    )
    total_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount_projected: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    committed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    items: Mapped[List["BillingRunItem"]] = relationship(
        "BillingRunItem",
        back_populates="billing_run",
        cascade="all, delete-orphan",
    )


class BillingRunItem(Base, UUIDPrimaryKeyMixin):
    """
    Granular per-subscription evaluation line for Billing Control Tower.
    Allows inspection, anomaly detection, variance explanation, and safe review.
    """
    __tablename__ = "billing_run_items"

    billing_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    expected_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expected_tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    expected_discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    expected_total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    prior_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    prior_invoice_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    variance_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    variance_reasons: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)

    status: Mapped[BillingRunItemStatus] = mapped_column(
        Enum(BillingRunItemStatus, native_enum=False, length=20),
        default=BillingRunItemStatus.PENDING,
        nullable=False,
    )
    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resulting_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("subscription_id", "billing_run_id", name="uq_billing_run_subscription"),
    )

    # Relationships
    billing_run: Mapped["BillingRun"] = relationship("BillingRun", back_populates="items")
    subscription: Mapped["Subscription"] = relationship("Subscription")
