from decimal import Decimal

from django.db import transaction

from apps.wallet.domain.reference_type import WalletReferenceType
from apps.wallet.domain.transaction_type import WalletTransactionType
from apps.wallet.models.wallet_account import WalletAccount
from apps.wallet.models.wallet_transaction import WalletTransaction
from apps.wallet.repositories.wallet_repository import WalletRepository

# Same single-implicit-currency decision as apps.payments.services.payment_service
# (DEFAULT_CURRENCY) -- no multi-currency requirement exists anywhere in this codebase yet.
DEFAULT_CURRENCY = "USD"

__all__ = ["WalletService", "InsufficientBalanceError", "DEFAULT_CURRENCY"]


class InsufficientBalanceError(Exception):
    """Raised by `debit()` when the wallet's locked balance is below the requested amount.
    The balance is never left partially mutated: the whole check-then-write happens inside one
    `transaction.atomic()` block holding a `select_for_update()` lock on the `WalletAccount`
    row, so a failed debit leaves both `balance` and the ledger exactly as they were."""


class WalletService:
    def __init__(self, *, repository: WalletRepository | None = None) -> None:
        self._wallets = repository or WalletRepository()

    def get_or_create_wallet(
        self, *, customer_id: int, currency: str = DEFAULT_CURRENCY
    ) -> WalletAccount:
        return self._wallets.get_or_create_for_customer(customer_id=customer_id, currency=currency)

    def list_transactions(self, wallet_id: int) -> list[WalletTransaction]:
        return self._wallets.list_transactions(wallet_id)

    def credit(
        self,
        *,
        customer_id: int,
        amount: Decimal,
        reference_type: WalletReferenceType,
        reference_id: int | None,
        currency: str = DEFAULT_CURRENCY,
    ) -> WalletAccount:
        """The only way `WalletAccount.balance` ever increases (Issue #199 Security
        Requirements) -- always inside the same transaction as the `WalletTransaction` ledger
        insert, never one without the other."""
        with transaction.atomic():
            created = self._wallets.get_or_create_for_customer(
                customer_id=customer_id, currency=currency
            )
            wallet = self._wallets.get_locked_by_id(created.pk)
            new_balance = wallet.balance + amount
            self._wallets.create_transaction(
                wallet=wallet,
                type=WalletTransactionType.CREDIT,
                amount=amount,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            self._wallets.save_balance(wallet, new_balance=new_balance)
        wallet.balance = new_balance
        return wallet

    def debit(
        self,
        *,
        customer_id: int,
        amount: Decimal,
        reference_type: WalletReferenceType,
        reference_id: int | None,
    ) -> WalletAccount:
        """The only way `WalletAccount.balance` ever decreases (Issue #199 Security
        Requirements). `select_for_update()` locks the row for the lifetime of this
        transaction, so two concurrent debits against the same wallet serialize: the second
        one re-reads the already-decremented balance set by the first before deciding whether
        it can proceed, which is exactly what prevents an overdraw under concurrency."""
        with transaction.atomic():
            wallet = self._wallets.get_locked_for_customer(customer_id)
            if wallet is None or wallet.balance < amount:
                raise InsufficientBalanceError(customer_id)
            new_balance = wallet.balance - amount
            self._wallets.create_transaction(
                wallet=wallet,
                type=WalletTransactionType.DEBIT,
                amount=amount,
                reference_type=reference_type,
                reference_id=reference_id,
            )
            self._wallets.save_balance(wallet, new_balance=new_balance)
        wallet.balance = new_balance
        return wallet
