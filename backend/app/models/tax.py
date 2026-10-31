from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class TaxRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Admin-configured tax rules (e.g., GST 18%, VAT 20%)."""
    __tablename__ = "tax_rules"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    rate_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("rate_percentage >= 0 AND rate_percentage <= 100", name="chk_tax_rate_range"),
    )

