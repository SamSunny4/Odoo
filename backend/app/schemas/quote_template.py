import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TemplateLineSchema(BaseModel):
    product_id: uuid.UUID
    product_variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, ge=1)


class TemplateLineResponse(BaseModel):
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_variant_id: Optional[uuid.UUID] = None
    variant_name: Optional[str] = None
    quantity: int
    unit_price: Decimal = Decimal("0.00")


class QuotationTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    validity_days: int = Field(default=30, ge=1, le=365)
    default_plan_id: Optional[uuid.UUID] = None
    default_lines: List[TemplateLineSchema] = []


class QuotationTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    validity_days: Optional[int] = Field(None, ge=1, le=365)
    default_plan_id: Optional[uuid.UUID] = None
    default_lines: Optional[List[TemplateLineSchema]] = None


class QuotationTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    validity_days: int
    default_plan_id: Optional[uuid.UUID] = None
    default_plan_name: Optional[str] = None
    default_lines: List[dict] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

