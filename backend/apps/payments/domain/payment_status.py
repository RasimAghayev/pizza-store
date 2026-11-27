from enum import StrEnum


class PaymentStatus(StrEnum):
    """Reused by `Payment.status`'s `choices=` (`models/payment.py`), same pattern as
    `apps.orders.domain.state_machine.OrderStatus` -> `Order.status`. `REFUNDED`/
    `PARTIALLY_REFUNDED` have no writer in this Task -- Issue #200 is the first real caller."""

    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
