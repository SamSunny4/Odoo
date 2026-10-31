import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentMethod
from app.schemas.pagination import PaginatedResponse


class PortalAddonLine(BaseModel):
    product_id: uuid.UUID
    product_variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(ge=1, le=10000)


class PortalSubscriptionActionRequest(BaseModel):
    action: Literal["pause", "resume", "cancel", "renew", "change_addons"]
    reason: Optional[str] = Field(None, max_length=500)
    renewal_duration_days: Optional[int] = Field(None, ge=1, le=3650)
    lines: Optional[list[PortalAddonLine]] = None


class PortalSubscriptionActionResponse(BaseModel):
    message: str
    status: str
    effective_date: Optional[date] = None
    cancel_at_period_end: bool = False


class PortalPaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    payment_date: date
    reference_note: Optional[str] = None
    is_reversed: bool


PortalPaymentPage = PaginatedResponse[PortalPaymentResponse]


class PortalAddonVariantResponse(BaseModel):
    id: uuid.UUID
    name: str
    price_adjustment: Decimal


class PortalAddonProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    sales_price: Decimal
    variants: list[PortalAddonVariantResponse]


class OutboxMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    message_type: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    status: str
    retry_count: int
    max_retries: int
    last_error: Optional[str] = None
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    created_at: datetime
