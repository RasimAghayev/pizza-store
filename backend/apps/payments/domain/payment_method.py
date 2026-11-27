from enum import StrEnum


class PaymentMethod(StrEnum):
    """Keys into `domain/gateway_registry.py`'s gateway registry and into `Payment.gateway`'s
    `choices=` (`models/payment.py`) -- one registry key per concrete `PaymentGateway`
    implementation."""

    CASH_ON_DELIVERY = "cash_on_delivery"
    MOCK_ONLINE = "mock_online"
    # Registered at runtime by apps.wallet.apps.WalletConfig.ready() via register_gateway()
    # below, never imported here -- apps.payments must not depend on apps.wallet (Issue #199
    # Architecture Requirements; ADR 0004 one-way dependency direction).
    WALLET = "wallet"
