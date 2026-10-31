import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class TaxRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    rate_percentage: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"))
    is_active: bool = True


class TaxRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rate_percentage: Optional[Decimal] = Field(None, ge=Decimal("0.00"), le=Decimal("100.00"))
    is_active: Optional[bool] = None


class TaxRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rate_percentage: Decimal
    is_active: bool
    created_at: Optional[datetime] = None

