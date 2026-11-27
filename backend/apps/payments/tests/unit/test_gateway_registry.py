import pytest

from apps.payments.domain.cash_on_delivery_gateway import CashOnDeliveryGateway
from apps.payments.domain.gateway_registry import UnknownPaymentMethodError, get_gateway
from apps.payments.domain.mock_online_gateway import MockOnlineGateway
from apps.payments.domain.payment_method import PaymentMethod


def test_get_gateway_returns_cash_on_delivery():
    assert isinstance(get_gateway(PaymentMethod.CASH_ON_DELIVERY), CashOnDeliveryGateway)


def test_get_gateway_returns_mock_online():
    assert isinstance(get_gateway(PaymentMethod.MOCK_ONLINE), MockOnlineGateway)


def test_get_gateway_raises_for_an_unknown_method():
    with pytest.raises(UnknownPaymentMethodError):
        get_gateway("some_unregistered_method")
