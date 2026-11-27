from apps.payments.domain.cash_on_delivery_gateway import CashOnDeliveryGateway
from apps.payments.domain.gateway import PaymentGateway
from apps.payments.domain.mock_online_gateway import MockOnlineGateway
from apps.payments.domain.payment_method import PaymentMethod

__all__ = ["UnknownPaymentMethodError", "get_gateway"]


class UnknownPaymentMethodError(Exception):
    pass


_GATEWAYS: dict[str, PaymentGateway] = {
    PaymentMethod.CASH_ON_DELIVERY: CashOnDeliveryGateway(),
    PaymentMethod.MOCK_ONLINE: MockOnlineGateway(),
}


def get_gateway(payment_method: str) -> PaymentGateway:
    """A small dict registry keyed by `payment_method` (Issue #198 Architecture Requirements)
    so a later Wallet Task (#199) can register a third gateway here without this function's
    callers needing to change."""
    try:
        return _GATEWAYS[payment_method]
    except KeyError:
        raise UnknownPaymentMethodError(payment_method) from None
