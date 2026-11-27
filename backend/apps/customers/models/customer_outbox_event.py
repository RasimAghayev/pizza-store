from shared.events.outbox import AbstractOutboxEvent


class CustomerOutboxEvent(AbstractOutboxEvent):
    """`customers`' own outbox_events table (ADR 0005). Relayed by
    shared/events/relay.py::relay_pending via
    `manage.py relay_outbox --model customers.CustomerOutboxEvent --exchange customers.events`
    (shared/management/commands/relay_outbox.py). First row type: CustomerRegistered -- see
    apps/customers/events/customer_registered.py."""
