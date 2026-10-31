import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    String, Numeric, Integer, Date, DateTime, Enum, ForeignKey, Text, JSON, and_, case,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin
from app.core.clock import organization_today

if TYPE_CHECKING:
    from app.models.customer import CustomerAccount
    from app.models.subscription import Subscription
    from app.models.payment import Payment


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PAID = "paid"
    CANCELLED = "cancelled"


class SendStatus(str, enum.Enum):
    NOT_SENT = "not_sent"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Immutable legal & financial document issued to customer.
    Includes full snapshot of customer details, addresses, and line calculations.
    """
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    billing_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, length=20),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )

    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    send_status: Mapped[SendStatus] = mapped_column(
        Enum(SendStatus, native_enum=False, length=20),
        default=SendStatus.NOT_SENT,
        nullable=False,
    )

    # Historical snapshots
    customer_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    billing_address_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("paid_amount >= 0", name="chk_invoice_paid_amount_non_neg"),
        CheckConstraint("total_amount >= 0", name="chk_invoice_total_amount_non_neg"),
    )

    # Relationships
    customer_account: Mapped["CustomerAccount"] = relationship(
        "CustomerAccount",
        back_populates="invoices",
    )
    subscription: Mapped["Subscription"] = relationship("Subscription")
    lines: Mapped[List["InvoiceLine"]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
    )

    @hybrid_property
    def outstanding_balance(self) -> Decimal:
        """Remaining balance on the invoice."""
        return max(Decimal("0.00"), self.total_amount - self.paid_amount)

    @outstanding_balance.expression
    def outstanding_balance(cls):
        return case(
            (cls.total_amount > cls.paid_amount, cls.total_amount - cls.paid_amount),
            else_=Decimal("0.00"),
        )

    @hybrid_property
    def is_overdue(self) -> bool:
        """Derived dynamically from due date and balance."""
        return (
            self.status == InvoiceStatus.CONFIRMED
            and organization_today() > self.due_date
            and self.outstanding_balance > Decimal("0.00")
        )

    @is_overdue.expression
    def is_overdue(cls):
        return and_(
            cls.status == InvoiceStatus.CONFIRMED,
            cls.due_date < organization_today(),
            cls.paid_amount < cls.total_amount,
        )


class InvoiceLine(Base, UUIDPrimaryKeyMixin):
    """
    Immutable line item snapshot on an issued invoice.
    Freezes all product details, rates, and discounts.
    """
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    tax_rule_name_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tax_rate_snapshot: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)

    discount_rule_name_snapshot: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")

