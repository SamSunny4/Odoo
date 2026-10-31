import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.subscription import SubscriptionStatus


class SubscriptionLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: Optional[str] = None
    variant_name: Optional[str] = None
    quantity: int
    unit_price: Decimal


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
    next_billing_date: Optional[date] = None
    billing_anchor_day: int
    payment_terms_days: int
    total_amount: Decimal = Decimal("0.00")
    lines: List[SubscriptionLineResponse] = []
