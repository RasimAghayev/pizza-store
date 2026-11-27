from decimal import Decimal

# calls apps.payments.domain.gateway_registry.get_gateway() -- see
# backend/apps/payments/README.md and backend/apps/wallet/README.md. Reuses Issue #198's
# gateway abstraction to actually collect the top-up amount (cash_on_delivery/mock_online);
# never touches apps.payments.models.Payment or PaymentService, since a top-up has no Order to
# attach a Payment row to (Issue #199 Architecture Requirements). apps.wallet depends on
# apps.payments; apps.payments never imports from apps.wallet (ADR 0004).
from apps.payments.domain.gateway_registry import get_gateway
from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.models.wallet_account import WalletAccount
from apps.wallet.services.wallet_service import DEFAULT_CURRENCY, WalletService

__all__ = ["TopUpService", "TopUpFailedError"]


class TopUpFailedError(Exception):
    """Raised when the funding gateway declines the top-up charge -- `failure_reason` carries
    the gateway's own reason string (same shape as `apps.payments.domain.gateway.
    AuthorizationResult`/`CaptureResult`). The wallet ledger is never touched on this path: the
    charge failing means there is nothing to credit (Issue #199 Security Requirements)."""

    def __init__(self, failure_reason: str | None) -> None:
        self.failure_reason = failure_reason
        super().__init__(failure_reason)


class TopUpService:
    def __init__(self, *, wallet_service: WalletService | None = None) -> None:
        self._wallets = wallet_service or WalletService()

    def top_up(
        self,
        *,
        customer_id: int,
        amount: Decimal,
        payment_method: str,
        payment_method_token: str | None,
        idempotency_key: str,
    ) -> WalletAccount:
        """Charges `amount` through the funding gateway, then credits the wallet by the same
        amount -- only on a successful authorize+capture; a declined charge raises
        `TopUpFailedError` before the ledger is ever touched."""
        gateway = get_gateway(payment_method)
        authorization = gateway.authorize(
            amount=amount,
            currency=DEFAULT_CURRENCY,
            payment_method_token=payment_method_token,
            idempotency_key=idempotency_key,
            customer_id=customer_id,
        )
        if not authorization.success:
            raise TopUpFailedError(authorization.failure_reason)

        capture = gateway.capture(authorization_id=authorization.authorization_id, amount=amount)
        if not capture.success:
            raise TopUpFailedError(capture.failure_reason)

        return self._wallets.credit(
            customer_id=customer_id,
            amount=amount,
            reference_type=WalletReferenceType.TOPUP,
            reference_id=None,
        )
