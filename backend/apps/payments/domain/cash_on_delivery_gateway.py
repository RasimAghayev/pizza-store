import uuid
from decimal import Decimal

from apps.payments.domain.gateway import (
    AuthorizationResult,
    CaptureResult,
    PaymentGateway,
    RefundResult,
)


class CashOnDeliveryGateway(PaymentGateway):
    """Cash is collected physically later, outside this system's accounting until Issue
    #199's reconciliation -- there is nothing to hold or settle electronically, so authorize
    and capture are both immediate, unconditional successes. `payment_method_token` is
    ignored entirely: a client never sends one for this method
    (`api/serializers.py::PaymentCaptureRequestSerializer`)."""

    def authorize(
        self,
        *,
        amount: Decimal,
        currency: str,
        payment_method_token: str | None,
        idempotency_key: str,
        customer_id: int,
    ) -> AuthorizationResult:
        return AuthorizationResult(
            success=True,
            authorization_id=f"cod_auth_{uuid.uuid4()}",
            provider_reference="cash_on_delivery",
        )

    def capture(self, *, authorization_id: str, amount: Decimal) -> CaptureResult:
        return CaptureResult(
            success=True,
            capture_id=f"cod_capture_{uuid.uuid4()}",
            provider_reference="cash_on_delivery",
        )

    def refund(self, *, capture_id: str, amount: Decimal, customer_id: int) -> RefundResult:
        return RefundResult(
            success=True,
            refund_id=f"cod_refund_{uuid.uuid4()}",
            provider_reference="cash_on_delivery",
        )
