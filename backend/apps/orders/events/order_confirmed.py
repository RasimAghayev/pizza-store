"""OrderConfirmed domain event (ADR 0005) -- docs/messaging/event-catalog.md's `orders.events`
/ `order.confirmed.v1` row. Published via an `OrderOutboxEvent` row
(apps/orders/models/order_outbox_event.py) inside the same DB transaction as the status
change, by `OrderService.transition()` whenever `to_status` is `OrderStatus.CONFIRMED` --
never by checkout, which only ever creates an order in `PENDING_PAYMENT`. Relayed by
`manage.py relay_outbox --model orders.OrderOutboxEvent --exchange orders.events`
(shared/management/commands/relay_outbox.py)."""

from dataclasses import dataclass

EXCHANGE = "orders.events"
EVENT_TYPE = "order.confirmed"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OrderConfirmedPayload:
    order_id: int
    customer_id: int
    confirmed_at: str
