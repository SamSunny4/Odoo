import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.subscription import SubscriptionStatus


class SubscriptionLineCreate(BaseModel):
    product_id: uuid.UUID
    product_variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, ge=1)
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0.00"))
    tax_rule_id: Optional[uuid.UUID] = None


class SubscriptionLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    product_variant_id: Optional[uuid.UUID] = None
    variant_name: Optional[str] = None
    quantity: int
    unit_price: Decimal
    tax_rule_id: Optional[uuid.UUID] = None
    tax_rate: Optional[Decimal] = None
    line_subtotal: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    line_total: Decimal = Decimal("0.00")


class SubscriptionPlanChargeResponse(BaseModel):
    quantity: int = 1
    unit_price: Decimal
    subtotal: Decimal
    discount_amount: Decimal = Decimal("0.00")
    tax_name: Optional[str] = None
    tax_rate: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    line_total: Decimal = Decimal("0.00")


class SubscriptionCreate(BaseModel):
    customer_account_id: uuid.UUID
    plan_id: uuid.UUID
    template_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quote_valid_until: Optional[date] = None
    billing_anchor_day: Optional[int] = Field(None, ge=1, le=31)
    payment_terms_days: int = Field(default=15, ge=0)
    status: SubscriptionStatus = SubscriptionStatus.DRAFT
    lines: List[SubscriptionLineCreate] = []

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.expiry_date and self.start_date > self.expiry_date:
            raise ValueError("start_date cannot be after expiry_date")
        if self.status not in (SubscriptionStatus.DRAFT, SubscriptionStatus.QUOTATION):
            raise ValueError("Subscriptions must be created as draft or quotation; use lifecycle actions to advance status")
        return self


class SubscriptionUpdate(BaseModel):
    plan_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    quote_valid_until: Optional[date] = None
    billing_anchor_day: Optional[int] = Field(None, ge=1, le=31)
    payment_terms_days: Optional[int] = Field(None, ge=0)
    lines: Optional[List[SubscriptionLineCreate]] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.expiry_date and self.start_date > self.expiry_date:
            raise ValueError("start_date cannot be after expiry_date")
        return self


class SubscriptionStatusAction(BaseModel):
    action: str = Field(..., description="Action: issue_quote, confirm, activate, pause, resume, renew, close")
    reason: Optional[str] = None
    renewal_duration_days: Optional[int] = Field(None, ge=1)


class SubscriptionAuditItem(BaseModel):
    id: uuid.UUID
    action: str
    changes: Dict[str, Any] = {}
    actor_user_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    timestamp: datetime


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_number: str
    customer_account_id: uuid.UUID
    customer_name: Optional[str] = None
    plan_id: uuid.UUID
    plan_name: Optional[str] = None
    status: SubscriptionStatus
    start_date: date
    expiry_date: Optional[date] = None
    quote_valid_until: Optional[date] = None
    next_billing_date: Optional[date] = None
    billing_anchor_day: int
    payment_terms_days: int
    plan_charge: Optional[SubscriptionPlanChargeResponse] = None
    subtotal_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    calculation_warnings: List[str] = []
    lines: List[SubscriptionLineResponse] = []


class SubscriptionDetailResponse(SubscriptionResponse):
    customer_billing_email: Optional[str] = None
    customer_address: Optional[str] = None
    plan_cadence: Optional[str] = None
    plan_base_price: Decimal = Decimal("0.00")
    plan_allow_pause: bool = True
    plan_allow_early_close: bool = True
    plan_allow_renewal: bool = True
    plan_auto_close_on_expiry: bool = False
    audit_history: List[SubscriptionAuditItem] = []
