from decimal import Decimal

from apps.payments.domain.mock_online_gateway import DECLINE_TOKEN, MockOnlineGateway


def test_authorize_succeeds_with_a_normal_token():
    result = MockOnlineGateway().authorize(
        amount=Decimal("12.50"),
        currency="USD",
        payment_method_token="tok_visa",
        idempotency_key="k1",
    )

    assert result.success is True
    assert result.authorization_id
    assert result.failure_reason is None


def test_authorize_fails_with_the_decline_token():
    result = MockOnlineGateway().authorize(
        amount=Decimal("12.50"),
        currency="USD",
        payment_method_token=DECLINE_TOKEN,
        idempotency_key="k2",
    )

    assert result.success is False
    assert result.failure_reason == "card_declined"


def test_authorize_fails_with_no_token():
    result = MockOnlineGateway().authorize(
        amount=Decimal("12.50"), currency="USD", payment_method_token=None, idempotency_key="k3"
    )

    assert result.success is False
    assert result.failure_reason == "missing_payment_method_token"


def test_capture_succeeds_and_carries_the_authorization_id_as_its_provider_reference():
    result = MockOnlineGateway().capture(authorization_id="mock_auth_1", amount=Decimal("12.50"))

    assert result.success is True
    assert result.provider_reference == "mock_auth_1"


def test_refund_succeeds():
    result = MockOnlineGateway().refund(capture_id="mock_capture_1", amount=Decimal("12.50"))

    assert result.success is True
    assert result.refund_id
