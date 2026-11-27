import uuid
from decimal import Decimal

# calls apps.payments.domain.gateway.PaymentGateway/AuthorizationResult/CaptureResult/
# RefundResult, apps.payments.domain.gateway_registry.register_gateway() -- see
# backend/apps/payments/README.md. Registered by apps/wallet/apps.py::WalletConfig.ready()
# (Issue #199). apps.wallet depends on apps.payments; apps.payments never imports from
# apps.wallet (ADR 0004 one-way dependency direction).
from apps.payments.domain.gateway import (
    AuthorizationResult,
    CaptureResult,
    PaymentGateway,
    RefundResult,
)
from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.services.wallet_service import InsufficientBalanceError, WalletService


class WalletGateway(PaymentGateway):
    """Pays an order out of the customer's own `WalletAccount` balance instead of an external
    provider (Issue #199). There is no separate hold/settle distinction for an in-process
    ledger debit the way there is for a real PSP, so `authorize()` performs the actual debit
    immediately; `capture()` is then a no-op that just reports the authorization as already
    settled, since `PaymentService.capture_for_order()` (Issue #198) always calls both in
    sequence and there is nothing left to do by the time `capture()` runs. `refund()` credits
    the wallet back -- the first and, as of this Task, only real caller of `WalletService.credit()`
    for a `refund` reference.

    Resolves this Task's own interface gap: `PaymentGateway.authorize()`/`refund()` carry no
    order/payment id, only `amount`/`currency`/`payment_method_token`/`idempotency_key`
    (`customer_id`, since Issue #199), so there is nothing here to pass as
    `WalletTransaction.reference_id` for an order-payment debit or a refund credit. Rather than
    widen the gateway interface further for traceability alone, `reference_id` is left `None`
    for both -- `reference_type` (`order_payment`/`refund`) already categorizes the entry, and
    nothing in Issue #199's Acceptance Criteria (ledger-equals-balance reconciliation, no
    overdraft under concurrency) depends on `reference_id` being populated. Revisit if a later
    Task needs to join a wallet ledger row back to a specific `Order`/`Payment`."""

    def authorize(
        self,
        *,
        amount: Decimal,
        currency: str,
        payment_method_token: str | None,
        idempotency_key: str,
        customer_id: int,
    ) -> AuthorizationResult:
        try:
            WalletService().debit(
                customer_id=customer_id,
                amount=amount,
                reference_type=WalletReferenceType.ORDER_PAYMENT,
                reference_id=None,
            )
        except InsufficientBalanceError:
            return AuthorizationResult(
                success=False,
                authorization_id="",
                provider_reference="",
                failure_reason="insufficient_wallet_balance",
            )
        return AuthorizationResult(
            success=True,
            authorization_id=f"wallet_auth_{uuid.uuid4()}",
            provider_reference="wallet",
        )

    def capture(self, *, authorization_id: str, amount: Decimal) -> CaptureResult:
        return CaptureResult(
            success=True, capture_id=f"wallet_capture_{uuid.uuid4()}", provider_reference="wallet"
        )

    def refund(self, *, capture_id: str, amount: Decimal, customer_id: int) -> RefundResult:
        WalletService().credit(
            customer_id=customer_id,
            amount=amount,
            reference_type=WalletReferenceType.REFUND,
            reference_id=None,
        )
        return RefundResult(
            success=True, refund_id=f"wallet_refund_{uuid.uuid4()}", provider_reference="wallet"
        )
