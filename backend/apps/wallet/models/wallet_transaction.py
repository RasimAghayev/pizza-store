from django.db import models

from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.domain.transaction_type import WalletTransactionType

_TYPE_CHOICES = [(t.value, t.value) for t in WalletTransactionType]
_REFERENCE_TYPE_CHOICES = [(r.value, r.value) for r in WalletReferenceType]


class WalletTransaction(models.Model):
    """Append-only ledger row (Issue #199) -- never updated or deleted after creation, only
    ever inserted by `services/wallet_service.py::WalletService`, always in the same
    `transaction.atomic()` block as the matching `WalletAccount.balance` update. `amount` is
    always stored positive; the sign is implied entirely by `type`. `reference_id` is a plain
    field (not a cross-app FK) meant to point at the row named by `reference_type` (e.g. a
    `Payment.pk` for `order_payment`/`refund`), but is left `None` by every writer in this Task
    -- `WalletGateway`'s `authorize()`/`refund()` (`domain/wallet_gateway.py`) have no such id
    available from Issue #198's `PaymentGateway` interface, and a direct top-up
    (`services/topup_service.py::TopUpService`) has no row to point at either. `reference_type`
    alone already categorizes each entry; revisit if a later Task needs to join a ledger row
    back to a specific `Order`/`Payment`."""

    wallet = models.ForeignKey(
        "wallet.WalletAccount", on_delete=models.CASCADE, related_name="transactions"
    )
    type = models.CharField(max_length=10, choices=_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_type = models.CharField(max_length=20, choices=_REFERENCE_TYPE_CHOICES)
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"WalletTransaction(id={self.pk}, type={self.type}, amount={self.amount})"
