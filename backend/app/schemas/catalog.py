import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.catalog import ProductType
from app.models.plan import BillingCadence


# Variant Schemas
class ProductVariantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_adjustment: Decimal = Field(default=Decimal("0.00"))
    is_active: bool = True


class ProductVariantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price_adjustment: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductVariantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    price_adjustment: Decimal
    is_active: bool


# Product Schemas
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: ProductType = ProductType.SERVICE
    sales_price: Decimal = Field(..., ge=Decimal("0.00"))
    cost_price: Decimal = Field(..., ge=Decimal("0.00"))
    notes: Optional[str] = None
    is_active: bool = True
    variants: Optional[List[ProductVariantCreate]] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[ProductType] = None
    sales_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    cost_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: ProductType
    sales_price: Decimal
    cost_price: Optional[Decimal] = None  # None when requested by Staff/Customer
    notes: Optional[str] = None
    is_active: bool
    variants: List[ProductVariantResponse] = []


# Plan Schemas
class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    cadence: BillingCadence
    base_price: Decimal = Field(..., ge=Decimal("0.00"))
    min_quantity: int = Field(default=1, ge=1)
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    auto_close_on_expiry: bool = False
    allow_early_close: bool = True
    allow_pause: bool = True
    allow_renewal: bool = True
    is_active: bool = True

    @model_validator(mode="after")
    def validate_plan_policies(self):
        if self.available_from and self.available_to and self.available_from > self.available_to:
            raise ValueError("available_from date cannot be after available_to date")
        if self.allow_renewal is False and self.auto_close_on_expiry is False:
            raise ValueError("Incompatible policies: plan must either allow renewal or enable auto-close upon expiry.")
        return self


class PlanUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    cadence: Optional[BillingCadence] = None
    base_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    min_quantity: Optional[int] = Field(None, ge=1)
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    auto_close_on_expiry: Optional[bool] = None
    allow_early_close: Optional[bool] = None
    allow_pause: Optional[bool] = None
    allow_renewal: Optional[bool] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_plan_policies(self):
        if self.available_from and self.available_to and self.available_from > self.available_to:
            raise ValueError("available_from date cannot be after available_to date")
        if self.allow_renewal is False and self.auto_close_on_expiry is False:
            raise ValueError("Incompatible policies: plan must either allow renewal or enable auto-close upon expiry.")
        return self


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    cadence: BillingCadence
    base_price: Decimal
    min_quantity: int
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    auto_close_on_expiry: bool
    allow_early_close: bool
    allow_pause: bool
    allow_renewal: bool
    is_active: bool


# Price Calculation Preview Schemas
class CalculatePreviewLine(BaseModel):
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, ge=1)
    tax_rule_id: Optional[uuid.UUID] = None


class CalculatePreviewRequest(BaseModel):
    plan_id: Optional[uuid.UUID] = None
    product_lines: List[CalculatePreviewLine] = []
    discount_rule_id: Optional[uuid.UUID] = None
    default_tax_rule_id: Optional[uuid.UUID] = None
    as_of: Optional[date] = None


class CalculatePreviewLineResponse(BaseModel):
    description: str
    product_name: str
    variant_name: Optional[str] = None
    price_adjustment: Decimal = Decimal("0.00")
    unit_price: Decimal
    quantity: int
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0.00")
    tax_rate: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    line_total: Decimal


class CalculatePreviewResponse(BaseModel):
    plan_name: Optional[str] = None
    plan_base_price: Decimal = Decimal("0.00")
    lines: List[CalculatePreviewLineResponse]
    subtotal: Decimal
    discount_amount: Decimal
    discount_name: Optional[str] = None
    tax_amount: Decimal
    total_amount: Decimal
    warnings: List[str] = []
