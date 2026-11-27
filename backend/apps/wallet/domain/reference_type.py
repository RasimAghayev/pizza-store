from enum import StrEnum


class WalletReferenceType(StrEnum):
    """What a `WalletTransaction` row is *for* -- `reference_id` points at the matching row in
    that other table (a plain field, not a cross-app FK, same pattern as
    `apps.payments.models.Payment.order_id`)."""

    TOPUP = "topup"
    ORDER_PAYMENT = "order_payment"
    REFUND = "refund"
