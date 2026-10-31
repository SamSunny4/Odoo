import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.models.invoice import InvoiceStatus, SendStatus
from app.models.payment import PaymentMethod


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    description: str
    product_name_snapshot: str
    variant_name_snapshot: Optional[str] = None
    quantity: int
    unit_price_snapshot: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    line_total: Decimal

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
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

    class Config:
        from_attributes = True


class RecordPaymentRequest(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod = PaymentMethod.BANK_TRANSFER
    payment_date: date
    reference_note: Optional[str] = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    payment_date: date
    reference_note: Optional[str] = None
    is_reversed: bool

    class Config:
        from_attributes = True

