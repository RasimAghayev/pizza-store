import uuid
from decimal import Decimal

from apps.payments.domain.gateway import (
    AuthorizationResult,
    CaptureResult,
    PaymentGateway,
    RefundResult,
)

# Test-double magic value, not a credential -- Bandit's B105 heuristic flags any string
# literal assigned to a name containing "token" (same false positive already suppressed in
# apps/identity/api/views.py).
DECLINE_TOKEN = "tok_decline"  # nosec B105


class MockOnlineGateway(PaymentGateway):
    """Simulates a real online PSP's authorize -> capture flow in-process, no real network
    call. `payment_method_token` is an opaque, already-tokenized string, as if tokenized
    client-side -- no card data (PAN/CVV/expiry) ever reaches this class or any other code in
    this Task (Issue #198 Security Requirements). Outcome is deterministic, driven by the
    token value itself -- the same magic-test-token convention every mainstream PSP sandbox
    uses to simulate a decline (e.g. Stripe's declined test card numbers), rather than
    randomness: a token exactly equal to `DECLINE_TOKEN` always fails; any other non-empty
    token succeeds."""

    def authorize(
        self,
        *,
        amount: Decimal,
        currency: str,
        payment_method_token: str | None,
        idempotency_key: str,
    ) -> AuthorizationResult:
        if not payment_method_token:
            return AuthorizationResult(
                success=False,
                authorization_id="",
                provider_reference="",
                failure_reason="missing_payment_method_token",
            )
        if payment_method_token == DECLINE_TOKEN:
            return AuthorizationResult(
                success=False,
                authorization_id="",
                provider_reference="",
                failure_reason="card_declined",
            )
        return AuthorizationResult(
            success=True,
            authorization_id=f"mock_auth_{uuid.uuid4()}",
            provider_reference=f"mock_pi_{uuid.uuid4()}",
        )

    def capture(self, *, authorization_id: str, amount: Decimal) -> CaptureResult:
        return CaptureResult(
            success=True,
            capture_id=f"mock_capture_{uuid.uuid4()}",
            provider_reference=authorization_id,
        )

    def refund(self, *, capture_id: str, amount: Decimal) -> RefundResult:
        return RefundResult(
            success=True,
            refund_id=f"mock_refund_{uuid.uuid4()}",
            provider_reference=capture_id,
        )
