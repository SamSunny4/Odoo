import uuid
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class QuotationTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Reusable quotation templates for sales staff to quickly prepare offers."""
    __tablename__ = "quotation_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    default_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Stored pre-configured lines: list of {product_id, variant_id, quantity}
    default_lines: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)

