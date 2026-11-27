"""CustomerRegistered domain event (ADR 0005) -- docs/messaging/event-catalog.md's
`customers.events` / `customer.registered.v1` row. Published via a `CustomerOutboxEvent` row
(apps/customers/models/customer_outbox_event.py) inside the same DB transaction as the
`Customer` row insert; relayed by
`manage.py relay_outbox --model customers.CustomerOutboxEvent --exchange customers.events`
(shared/management/commands/relay_outbox.py). First real event ever published through the
Phase 6 Outbox infrastructure (Issue #176)."""

from dataclasses import dataclass

EXCHANGE = "customers.events"
EVENT_TYPE = "customer.registered"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CustomerRegisteredPayload:
    user_id: int
    email: str
    registered_at: str
