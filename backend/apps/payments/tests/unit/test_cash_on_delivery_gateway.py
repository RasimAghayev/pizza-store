from decimal import Decimal

from apps.payments.domain.cash_on_delivery_gateway import CashOnDeliveryGateway


def test_authorize_always_succeeds():
    result = CashOnDeliveryGateway().authorize(
        amount=Decimal("12.50"), currency="USD", payment_method_token=None, idempotency_key="k1"
    )

    assert result.success is True
    assert result.authorization_id
    assert result.failure_reason is None


def test_capture_always_succeeds():
    result = CashOnDeliveryGateway().capture(authorization_id="cod_auth_1", amount=Decimal("12.50"))

    assert result.success is True
    assert result.capture_id


def test_refund_always_succeeds():
    result = CashOnDeliveryGateway().refund(capture_id="cod_capture_1", amount=Decimal("12.50"))

    assert result.success is True
    assert result.refund_id
