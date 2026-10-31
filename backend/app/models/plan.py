import enum
from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, Integer, Date, Enum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class BillingCadence(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Subscription plan governing price, billing cadence, and lifecycle policies."""
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cadence: Mapped[BillingCadence] = mapped_column(
        Enum(BillingCadence, native_enum=False, length=20),
        default=BillingCadence.MONTHLY,
        nullable=False,
    )
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Availability window
    available_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    available_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Lifecycle policies
    auto_close_on_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_early_close: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_pause: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_renewal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("base_price >= 0", name="chk_plan_base_price_non_neg"),
        CheckConstraint("min_quantity >= 1", name="chk_plan_min_quantity_pos"),
    )

