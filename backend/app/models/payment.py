import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    String, Numeric, Date, DateTime, Enum, ForeignKey, Text, Boolean,
    CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class PaymentMethod(str, enum.Enum):
    BANK_TRANSFER = "bank_transfer"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    OTHER = "other"


class Payment(Base, UUIDPrimaryKeyMixin):
    """
    Append-only payment record matching customer remittances against invoices.
    Payments are immutable; corrections require a PaymentReversal record.
    """
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, native_enum=False, length=30),
        default=PaymentMethod.BANK_TRANSFER,
        nullable=False,
    )
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recorded_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_payment_amount_positive"),
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")
    reversal: Mapped[Optional["PaymentReversal"]] = relationship(
        "PaymentReversal",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class PaymentReversal(Base, UUIDPrimaryKeyMixin):
    """
    Explicit reversal record for voided or refunded payments.
    Ensures complete financial auditability without modifying historical payments.
    """
    __tablename__ = "payment_reversals"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    reversal_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reversed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reversed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        CheckConstraint("reversal_amount > 0", name="chk_reversal_amount_positive"),
    )

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="reversal")

