from django.db import models


class WalletAccount(models.Model):
    """One balance per customer (Issue #199). `customer_id` is a plain field, not a cross-app
    FK, same pattern as `apps.orders.models.Order.customer_id`. `balance` is a denormalized
    cache of `WalletTransaction`'s running sum -- reconciled from the ledger, never written to
    directly outside `services/wallet_service.py::WalletService` (Security Requirements)."""

    customer_id = models.PositiveBigIntegerField(db_index=True, unique=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default="0.00")
    currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "wallet"

    def __str__(self) -> str:
        return (
            f"WalletAccount(id={self.pk}, customer_id={self.customer_id}, "
            f"balance={self.balance})"
        )
