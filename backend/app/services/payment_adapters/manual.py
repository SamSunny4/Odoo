import uuid
from decimal import Decimal
from typing import Any, Dict, Optional
from app.services.payment_adapters.base import BasePaymentAdapter, PaymentAdapterResult


class ManualPaymentAdapter(BasePaymentAdapter):
    """
    Default adapter for Phase 6 manual payment recording and reversals.
    Serves as the baseline implementation conforming to the provider adapter contract.
    """

    @property
    def provider_name(self) -> str:
        return "manual"

    async def process_payment(
        self,
        invoice_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        payment_method: str,
        reference_note: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentAdapterResult:
        ref = reference_note or f"MANUAL-{uuid.uuid4().hex[:8].upper()}"
        return PaymentAdapterResult(
            success=True,
            provider=self.provider_name,
            external_reference=ref,
            amount=amount,
            status="settled",
            message=f"Manual {payment_method} payment of {amount} {currency} recorded.",
            raw_response={"reference": ref, "metadata": metadata or {}},
        )

    async def process_refund(
        self,
        payment_id: uuid.UUID,
        amount: Decimal,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PaymentAdapterResult:
        ref = f"REV-{payment_id.hex[:8].upper()}"
        return PaymentAdapterResult(
            success=True,
            provider=self.provider_name,
            external_reference=ref,
            amount=amount,
            status="reversed",
            message=f"Manual reversal of {amount} processed: {reason}",
            raw_response={"payment_id": str(payment_id), "reason": reason, "metadata": metadata or {}},
        )

    async def handle_webhook(
        self,
        event_payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> PaymentAdapterResult:
        event_type = event_payload.get("event_type", "payment.created")
        amount = Decimal(str(event_payload.get("amount", "0.00")))
        ext_id = str(event_payload.get("external_id", uuid.uuid4().hex))

        return PaymentAdapterResult(
            success=True,
            provider=self.provider_name,
            external_reference=ext_id,
            amount=amount,
            status="settled" if "succeeded" in event_type or "created" in event_type else "processed",
            message=f"Webhook event {event_type} handled.",
            raw_response=event_payload,
        )

