import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency: str
    period: str = "this_month"
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    active_subscription_count: int
    monthly_recurring_revenue: Optional[Decimal] = None
    invoiced_revenue: Optional[Decimal] = None
    invoiced_mtd: Optional[Decimal] = None
    cash_collected: Optional[Decimal] = None
    cash_collected_mtd: Optional[Decimal] = None
    outstanding_balance: Optional[Decimal] = None
    overdue_balance: Optional[Decimal] = None
    overdue_invoice_count: int
    pending_quotes_count: int
    renewals_due_7d_count: int
    metric_definitions: Dict[str, str] = {
        "monthly_recurring_revenue": "Normalized monthly run rate of all active contracts (annualized/monthly normalized before tax and discounts).",
        "invoiced_revenue": "Total value of all legal financial demand invoices issued and confirmed within the selected date range.",
        "cash_collected": "Total actual cash remittances received against invoices within the selected date range, net of reversals/refunds.",
        "outstanding_balance": "Total unpaid balance remaining across all confirmed and open customer invoices as of today.",
        "overdue_balance": "Portion of unpaid invoice balances whose due date has lapsed without complete payment.",
    }


class DrillDownItemResponse(BaseModel):
    id: str
    entity_type: str  # "invoice", "payment", "subscription"
    reference_number: str
    customer_name: str
    customer_account_id: Optional[uuid.UUID] = None
    plan_name: Optional[str] = None
    date: date
    metric_category: str
    status: str
    currency: str
    amount: Decimal
    paid_amount: Optional[Decimal] = Decimal("0.00")
    balance: Optional[Decimal] = Decimal("0.00")


class DrillDownResponse(BaseModel):
    metric: str
    period_start: date
    period_end: date
    total_items: int
    total_amount: Decimal
    items: List[DrillDownItemResponse]
    page: int
    page_size: int
    total_pages: int
