import abc
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
from pydantic import BaseModel


class PaymentAdapterResult(BaseModel):
    success: bool
    provider: str
    external_reference: Optional[str] = None
    amount: Decimal
    status: str  # "settled", "pending", "failed", "reversed"
    message: str = ""
    raw_response: Dict[str, Any] = {}


class BasePaymentAdapter(abc.ABC):
    """
    Abstract adapter boundary for payment providers.
    Supports current manual payments and provides hooks for future provider integrations (Stripe, Adyen, Bank Feeds).
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Identifier of payment provider (e.g. 'manual', 'stripe', 'mock')."""
        pass

    @abc.abstractmethod
    async def process_payment(
        self,
        invoice_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        payment_method: str,
        reference_note: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentAdapterResult:
        """Process or record an inbound payment against an invoice."""
        pass

    @abc.abstractmethod
    async def process_refund(
        self,
        payment_id: uuid.UUID,
        amount: Decimal,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentAdapterResult:
        """Process or record a reversal/refund for a previously settled payment."""
        pass

    @abc.abstractmethod
    async def handle_webhook(
        self,
        event_payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> PaymentAdapterResult:
        """Handle inbound webhook callback from the payment provider."""
        pass

