from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AuthorizationResult:
    success: bool
    authorization_id: str
    provider_reference: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class CaptureResult:
    success: bool
    capture_id: str
    provider_reference: str
    failure_reason: str | None = None


@dataclass(frozen=True)
class RefundResult:
    success: bool
    refund_id: str
    provider_reference: str
    failure_reason: str | None = None


class PaymentGateway(ABC):
    """Issue #198 -- shape researched against a mainstream PSP's current manual-capture
    lifecycle (Stripe's PaymentIntents: `authorize` places a hold, moving the intent to a
    `requires_capture`-equivalent state; `capture` settles up to the authorized amount;
    `refund` reverses money already captured, documented at
    https://docs.stripe.com/payments/place-a-hold-on-a-payment-method, checked at
    implementation time per the research-before-implementing rule). Chosen so a later real
    provider only needs a new concrete class registered into `gateway_registry.py`, never a
    change to this interface or to `PaymentService`. `refund()` is implemented by every
    gateway here but has no caller yet in this Task -- Issue #199 is the first real caller."""

    @abstractmethod
    def authorize(
        self,
        *,
        amount: Decimal,
        currency: str,
        payment_method_token: str | None,
        idempotency_key: str,
    ) -> AuthorizationResult: ...

    @abstractmethod
    def capture(self, *, authorization_id: str, amount: Decimal) -> CaptureResult: ...

    @abstractmethod
    def refund(self, *, capture_id: str, amount: Decimal) -> RefundResult: ...
