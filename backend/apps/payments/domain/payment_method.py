from enum import StrEnum


class PaymentMethod(StrEnum):
    """Keys into `domain/gateway_registry.py`'s gateway registry and into `Payment.gateway`'s
    `choices=` (`models/payment.py`) -- one registry key per concrete `PaymentGateway`
    implementation."""

    CASH_ON_DELIVERY = "cash_on_delivery"
    MOCK_ONLINE = "mock_online"
