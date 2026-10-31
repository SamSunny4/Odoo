import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.discount import DiscountType, DiscountScope


class DiscountRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    discount_type: DiscountType
    value: Decimal = Field(..., gt=Decimal("0.00"))
    scope: DiscountScope = DiscountScope.SUBSCRIPTION
    target_product_id: Optional[uuid.UUID] = None
    min_spend: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    min_quantity: int = Field(default=0, ge=0)
    max_usage_limit: Optional[int] = Field(default=None, ge=1)
    valid_from: date
    valid_to: date
    is_active: bool = True

    @model_validator(mode="after")
    def validate_discount(self):
        if self.valid_from > self.valid_to:
            raise ValueError("valid_from date cannot be after valid_to date")
        if self.discount_type == DiscountType.PERCENTAGE and self.value > Decimal("100.00"):
            raise ValueError("Percentage discount value cannot exceed 100%")
        if self.scope == DiscountScope.PRODUCT and not self.target_product_id:
            raise ValueError("target_product_id is required when scope is set to 'product'")
        return self


class DiscountRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    discount_type: Optional[DiscountType] = None
    value: Optional[Decimal] = Field(None, gt=Decimal("0.00"))
    scope: Optional[DiscountScope] = None
    target_product_id: Optional[uuid.UUID] = None
    min_spend: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    min_quantity: Optional[int] = Field(None, ge=0)
    max_usage_limit: Optional[int] = Field(None, ge=1)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: Optional[bool] = None

class DiscountRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    discount_type: DiscountType
    value: Decimal
    scope: DiscountScope
    target_product_id: Optional[uuid.UUID] = None
    target_product_name: Optional[str] = None
    min_spend: Decimal
    min_quantity: int
    max_usage_limit: Optional[int] = None
    current_usage_count: int = 0
    valid_from: date
    valid_to: date
    is_active: bool
    created_at: Optional[datetime] = None

