"""OrderCreated domain event (ADR 0005) -- docs/messaging/event-catalog.md's `orders.events` /
`order.created.v1` row. Published via an `OrderOutboxEvent` row
(apps/orders/models/order_outbox_event.py) inside the same DB transaction as the
`Order`/`OrderItem`/initial `OrderStatusAudit` row inserts (see
`OrderService.checkout()`); relayed by
`manage.py relay_outbox --model orders.OrderOutboxEvent --exchange orders.events`
(shared/management/commands/relay_outbox.py). Money/timestamp fields are stringified --
`models.JSONField`'s default encoder cannot serialize `Decimal`/`datetime` directly."""

from dataclasses import dataclass

EXCHANGE = "orders.events"
EVENT_TYPE = "order.created"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OrderCreatedPayload:
    order_id: int
    customer_id: int
    branch_id: int
    total_amount: str
    created_at: str
