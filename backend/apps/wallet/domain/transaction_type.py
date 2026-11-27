from enum import StrEnum


class WalletTransactionType(StrEnum):
    """Reused by `WalletTransaction.type`'s `choices=`, same pattern as
    `apps.payments.domain.payment_status.PaymentStatus` -> `Payment.status`."""

    CREDIT = "credit"
    DEBIT = "debit"
