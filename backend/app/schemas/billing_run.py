import uuid
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.models.billing_run import BillingRunItemStatus


class ControlTowerItemResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_number: str
    customer_name: str
    plan_name: str
    expected_subtotal: Decimal
    expected_tax_amount: Decimal
    expected_discount_amount: Decimal
    expected_total_amount: Decimal
    prior_invoice_total: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    variance_reasons: List[str] = []
    warnings: List[str] = []
    status: BillingRunItemStatus
    skip_reason: Optional[str] = None


class ControlTowerPreviewResponse(BaseModel):
    billing_period_start: str
    billing_period_end: str
    total_subscriptions: int
    total_projected_amount: Decimal
    flagged_count: int
    items: List[ControlTowerItemResponse] = []


class CommitBatchResponse(BaseModel):
    billing_run_id: uuid.UUID
    invoices_created_count: int
    total_invoiced_amount: Decimal
    status: str

