import enum
import uuid
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Text, Numeric, Boolean, Enum, ForeignKey, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class ProductType(str, enum.Enum):
    SERVICE = "service"
    GOODS = "goods"
    CONSUMABLE = "consumable"


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Product catalog item."""
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[ProductType] = mapped_column(
        Enum(ProductType, native_enum=False, length=20),
        default=ProductType.SERVICE,
        nullable=False,
    )
    sales_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # Admin only
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_add_on: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("sales_price >= 0", name="chk_product_sales_price_non_neg"),
        CheckConstraint("cost_price >= 0", name="chk_product_cost_price_non_neg"),
    )

    # Relationships
    variants: Mapped[List["ProductVariant"]] = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
    )


class ProductVariant(Base, UUIDPrimaryKeyMixin):
    """Product variant providing price adjustments (e.g., Brand: Odoo adds +560)."""
    __tablename__ = "product_variants"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price_adjustment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="variants")

