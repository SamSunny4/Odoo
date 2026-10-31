import uuid
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.models.catalog import ProductType
from app.models.plan import BillingCadence


class ProductVariantResponse(BaseModel):
    id: uuid.UUID
    name: str
    price_adjustment: Decimal
    is_active: bool

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: ProductType
    sales_price: Decimal
    cost_price: Optional[Decimal] = None  # None when requested by Staff/Customer
    notes: Optional[str] = None
    is_active: bool
    variants: List[ProductVariantResponse] = []

    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    cadence: BillingCadence
    base_price: Decimal
    min_quantity: int
    auto_close_on_expiry: bool
    allow_early_close: bool
    allow_pause: bool
    allow_renewal: bool
    is_active: bool

    class Config:
        from_attributes = True

