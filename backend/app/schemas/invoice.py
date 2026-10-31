import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.invoice import InvoiceStatus, SendStatus
from app.models.payment import PaymentMethod


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    product_name_snapshot: str
    variant_name_snapshot: Optional[str] = None
    quantity: int
    unit_price_snapshot: Decimal
    subtotal: Decimal
    tax_rule_name_snapshot: Optional[str] = None
    tax_rate_snapshot: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")
    discount_rule_name_snapshot: Optional[str] = None
    discount_amount: Decimal = Decimal("0.00")
    line_total: Decimal


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    subscription_id: uuid.UUID
    customer_account_id: uuid.UUID
    customer_name: Optional[str] = None
    currency: str
    status: InvoiceStatus
    billing_period_start: date
    billing_period_end: date
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_balance: Decimal
    is_overdue: bool
    issue_date: date
    due_date: date
    send_status: SendStatus
    lines: List[InvoiceLineResponse] = []


class RecordPaymentRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    payment_date: date
    reference_note: Optional[str] = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    payment_date: date
    reference_note: Optional[str] = None
    is_reversed: bool


class GenerateDraftInvoiceRequest(BaseModel):
    subscription_id: uuid.UUID
    billing_period_start: Optional[date] = None
    billing_period_end: Optional[date] = None
    as_draft: bool = True


class CancelInvoiceRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Audit reason for invoice cancellation")


class InvoiceAuditItem(BaseModel):
    id: uuid.UUID
    action: str
    changes: Dict[str, Any] = {}
    actor_user_id: Optional[uuid.UUID] = None
    actor_name: str
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    timestamp: datetime


class InvoiceDetailResponse(InvoiceResponse):
    customer_snapshot: Dict[str, Any] = {}
    billing_address_snapshot: Dict[str, Any] = {}
    cancellation_reason: Optional[str] = None
    sent_at: Optional[datetime] = None
    payments: List[PaymentResponse] = []
    audit_history: List[InvoiceAuditItem] = []
