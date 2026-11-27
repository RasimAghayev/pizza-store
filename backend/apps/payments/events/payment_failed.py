"""PaymentFailed domain event (ADR 0005) -- docs/messaging/event-catalog.md's
`payments.events` / `payment.failed.v1` row (names reserved by master prompt S6). Published
via a `PaymentOutboxEvent` row inside the same DB transaction as the `Payment` row write and
the `Order` transition to `PAYMENT_FAILED` (see `PaymentService.capture_for_order()`)."""

from dataclasses import dataclass

EXCHANGE = "payments.events"
EVENT_TYPE = "payment.failed"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PaymentFailedPayload:
    payment_id: int
    order_id: int
    reason: str | None
