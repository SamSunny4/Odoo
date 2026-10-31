from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    currency: str
    active_subscription_count: int
    monthly_recurring_revenue: Optional[Decimal] = None
    invoiced_mtd: Optional[Decimal] = None
    cash_collected_mtd: Optional[Decimal] = None
    outstanding_balance: Optional[Decimal] = None
    overdue_balance: Optional[Decimal] = None
    overdue_invoice_count: int
    pending_quotes_count: int
    renewals_due_7d_count: int
