from shared.events.outbox import AbstractOutboxEvent


class OrderOutboxEvent(AbstractOutboxEvent):
    """`orders`' own outbox_events table (ADR 0005). Relayed by
    shared/events/relay.py::relay_pending via
    `manage.py relay_outbox --model orders.OrderOutboxEvent --exchange orders.events`
    (shared/management/commands/relay_outbox.py). Row types: OrderCreated (on checkout --
    see apps/orders/events/order_created.py) and OrderConfirmed (on transition to
    `OrderStatus.CONFIRMED` -- see apps/orders/events/order_confirmed.py)."""
