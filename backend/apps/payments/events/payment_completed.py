"""PaymentCompleted domain event (ADR 0005) -- docs/messaging/event-catalog.md's
`payments.events` / `payment.completed.v1` row (names reserved by master prompt S6). Published
via a `PaymentOutboxEvent` row (apps/payments/models/payment_outbox_event.py) inside the same
DB transaction as the `Payment` row write and the `Order` transition to `CONFIRMED` (see
`PaymentService.capture_for_order()`); relayed by
`manage.py relay_outbox --model payments.PaymentOutboxEvent --exchange payments.events`
(shared/management/commands/relay_outbox.py). `amount` is stringified -- `models.JSONField`'s
default encoder cannot serialize `Decimal` directly."""

from dataclasses import dataclass

EXCHANGE = "payments.events"
EVENT_TYPE = "payment.completed"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PaymentCompletedPayload:
    payment_id: int
    order_id: int
    amount: str
    currency: str
