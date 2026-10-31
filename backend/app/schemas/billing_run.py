import uuid
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.models.billing_run import BillingRunItemStatus


class ControlTowerItemResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_number: str
    billing_period_start: date
    billing_period_end: date
    customer_name: str
    plan_name: str
    expected_subtotal: Decimal
    expected_tax_amount: Decimal
    expected_discount_amount: Decimal
    expected_total_amount: Decimal
    prior_invoice_total: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    variance_reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    status: BillingRunItemStatus
    skip_reason: Optional[str] = None
    resulting_invoice_id: Optional[uuid.UUID] = None


class ControlTowerPreviewResponse(BaseModel):
    billing_run_id: uuid.UUID
    billing_period_start: date
    billing_period_end: date
    total_subscriptions: int
    total_projected_amount: Decimal
    flagged_count: int
    items: List[ControlTowerItemResponse] = Field(default_factory=list)


class CommitBatchRequest(BaseModel):
    approved_item_ids: List[uuid.UUID] = Field(min_length=1)


class CommitBatchResponse(BaseModel):
    billing_run_id: uuid.UUID
    invoices_created_count: int
    total_invoiced_amount: Decimal
    status: str
    failed_count: int = 0


class BillingRunSummaryResponse(BaseModel):
    id: uuid.UUID
    run_date: date
    billing_period_start: date
    billing_period_end: date
    status: str
    total_evaluated: int
    total_amount_projected: Decimal
    created_at: datetime
    committed_at: Optional[datetime] = None
    created_by_user_id: uuid.UUID
    committed_by_user_id: Optional[uuid.UUID] = None
    invoices_created_count: int = 0
    skipped_count: int = 0
    flagged_count: int = 0
    failed_count: int = 0


class SkipItemRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for skipping item")


class RetryItemResponse(BaseModel):
    id: uuid.UUID
    subscription_id: uuid.UUID
    status: BillingRunItemStatus
    warnings: List[str]
    expected_total_amount: Decimal
    message: str


class AutoBillResponse(BaseModel):
    status: str
    task_id: str
