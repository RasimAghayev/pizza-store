# Messaging

RabbitMQ topology, event naming convention, event schema/versioning, Outbox Pattern, retry/DLQ policy.

See [ADR 0005](../adr/0005-event-topology-and-outbox-design.md) for the exchange/queue/routing
key convention, event envelope and schema versioning, Outbox and idempotent-consumer design,
and DLQ/retry policy, and [event-catalog.md](event-catalog.md) for every event's assigned
routing key.

> Status: Phase 1 — topology and schema decided (ADR 0005); implementation is Phase 6.
