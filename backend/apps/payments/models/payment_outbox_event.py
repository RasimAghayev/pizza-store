from shared.events.outbox import AbstractOutboxEvent


class PaymentOutboxEvent(AbstractOutboxEvent):
    """`payments`' own outbox_events table (ADR 0005). Relayed by
    shared/events/relay.py::relay_pending via
    `manage.py relay_outbox --model payments.PaymentOutboxEvent --exchange payments.events`
    (shared/management/commands/relay_outbox.py). Row types: PaymentCompleted (on a successful
    capture -- see apps/payments/events/payment_completed.py) and PaymentFailed (on a failed
    authorization/capture -- see apps/payments/events/payment_failed.py)."""
