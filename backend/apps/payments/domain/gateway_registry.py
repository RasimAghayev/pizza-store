from apps.payments.domain.cash_on_delivery_gateway import CashOnDeliveryGateway
from apps.payments.domain.gateway import PaymentGateway
from apps.payments.domain.mock_online_gateway import MockOnlineGateway
from apps.payments.domain.payment_method import PaymentMethod

__all__ = ["UnknownPaymentMethodError", "get_gateway", "register_gateway"]


class UnknownPaymentMethodError(Exception):
    pass


_GATEWAYS: dict[str, PaymentGateway] = {
    PaymentMethod.CASH_ON_DELIVERY: CashOnDeliveryGateway(),
    PaymentMethod.MOCK_ONLINE: MockOnlineGateway(),
}


def get_gateway(payment_method: str) -> PaymentGateway:
    """A small dict registry keyed by `payment_method` (Issue #198 Architecture Requirements)."""
    try:
        return _GATEWAYS[payment_method]
    except KeyError:
        raise UnknownPaymentMethodError(payment_method) from None


def register_gateway(payment_method: str, gateway: PaymentGateway) -> None:
    """Lets another module add a gateway here without this module ever importing that other
    module -- called by `apps.wallet.apps.WalletConfig.ready()` to register `WalletGateway`
    as the `wallet` method (Issue #199 Architecture Requirements). `apps.payments` has no
    static import of `apps.wallet` anywhere; the dependency runs one way, wallet depending on
    payments, never the reverse (ADR 0004)."""
    _GATEWAYS[payment_method] = gateway
