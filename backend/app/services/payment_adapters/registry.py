from typing import Dict, Type
from app.services.payment_adapters.base import BasePaymentAdapter
from app.services.payment_adapters.manual import ManualPaymentAdapter

_ADAPTER_REGISTRY: Dict[str, Type[BasePaymentAdapter]] = {
    "manual": ManualPaymentAdapter,
}


def register_payment_adapter(name: str, adapter_cls: Type[BasePaymentAdapter]) -> None:
    _ADAPTER_REGISTRY[name.lower()] = adapter_cls


def get_payment_adapter(name: str = "manual") -> BasePaymentAdapter:
    adapter_cls = _ADAPTER_REGISTRY.get(name.lower(), ManualPaymentAdapter)
    return adapter_cls()

