from decimal import Decimal

from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.domain.transaction_type import WalletTransactionType
from apps.wallet.models.wallet_account import WalletAccount
from apps.wallet.models.wallet_transaction import WalletTransaction


class WalletRepository:
    def get_or_create_for_customer(self, *, customer_id: int, currency: str) -> WalletAccount:
        wallet, _created = WalletAccount.objects.get_or_create(
            customer_id=customer_id, defaults={"currency": currency}
        )
        return wallet

    def get_locked_for_customer(self, customer_id: int) -> WalletAccount | None:
        """Must be called inside an open `transaction.atomic()` block -- see
        `services/wallet_service.py::WalletService.debit()`/`credit()`. Locks the row until
        that transaction commits or rolls back (Issue #199 Architecture Requirements)."""
        return WalletAccount.objects.select_for_update().filter(customer_id=customer_id).first()

    def get_locked_by_id(self, wallet_id: int) -> WalletAccount:
        """Same locking contract as `get_locked_for_customer()`, by primary key -- used right
        after `get_or_create_for_customer()` in `WalletService.credit()`, where the row is
        already known to exist, so `.get()` (never `None`) avoids an unreachable null-check."""
        return WalletAccount.objects.select_for_update().get(pk=wallet_id)

    def save_balance(self, wallet: WalletAccount, *, new_balance: Decimal) -> None:
        wallet.balance = new_balance
        wallet.save(update_fields=["balance"])

    def create_transaction(
        self,
        *,
        wallet: WalletAccount,
        type: WalletTransactionType,
        amount: Decimal,
        reference_type: WalletReferenceType,
        reference_id: int | None,
    ) -> WalletTransaction:
        return WalletTransaction.objects.create(
            wallet=wallet,
            type=type,
            amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
        )

    def list_transactions(self, wallet_id: int) -> list[WalletTransaction]:
        return list(WalletTransaction.objects.filter(wallet_id=wallet_id))
