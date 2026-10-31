import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.payment import PaymentMethod


class PaymentReversalRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Mandatory audit reason for voiding or refunding payment")
    amount: Optional[Decimal] = Field(None, gt=0, description="Optional partial refund amount. If omitted, full payment amount is reversed.")


class PaymentReversalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    reversal_amount: Decimal
    reason: str
    reversed_by_user_id: uuid.UUID
    reversed_at: datetime


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    payment_date: date
    reference_note: Optional[str] = None
    is_reversed: bool = False
    created_at: Optional[datetime] = None
    reversal: Optional[PaymentReversalResponse] = None
    reversals: List[PaymentReversalResponse] = Field(default_factory=list)


class PaymentDetailResponse(PaymentResponse):
    customer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    currency: str = "USD"
    recorded_by_email: Optional[str] = None


class RecordPaymentRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, description="Payment amount must be greater than zero")
    payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    payment_date: date
    reference_note: Optional[str] = None


class CollectionItemResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str
    customer_account_id: uuid.UUID
    customer_name: str
    billing_email: Optional[str] = None
    total_amount: Decimal
    paid_amount: Decimal
    balance_due: Decimal
    currency: str
    issue_date: date
    due_date: date
    days_overdue: int
    aging_bucket: str  # "1-30 days", "31-60 days", "61-90 days", "90+ days"
    last_reminder_sent_at: Optional[datetime] = None


class AgingBucketSummary(BaseModel):
    count: int = 0
    amount: Decimal = Decimal("0.00")


class CollectionQueueSummary(BaseModel):
    total_overdue_balance: Decimal
    total_overdue_invoices: int
    aging_breakdown: Dict[str, AgingBucketSummary]
    items: List[CollectionItemResponse]


class SendOverdueReminderRequest(BaseModel):
    custom_message: Optional[str] = Field(None, max_length=1000)


class PaymentWebhookPayload(BaseModel):
    event_type: str = Field(..., description="e.g. charge.succeeded, charge.refunded")
    provider: str = Field("manual", description="Provider identifier, e.g. stripe, mock, manual")
    external_id: str
    invoice_number: Optional[str] = None
    amount: Decimal
    currency: str = "USD"
    metadata: Dict[str, Any] = {}

