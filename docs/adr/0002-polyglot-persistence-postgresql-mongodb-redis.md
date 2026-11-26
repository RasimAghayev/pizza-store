# ADR 0002: Polyglot Persistence — PostgreSQL, MongoDB, Redis

## Status

Accepted

## Context

The platform works with three kinds of data: (1) transactional data that requires strict
consistency (orders, payments, balances), (2) document data with a variable structure and low
query load (audit, event history, tracking history), (3) short-lived, frequently-read "hot"
data (cache, session, latest GPS coordinates).

A single database (PostgreSQL alone) could handle all three, but high-write-frequency,
schema-less data such as audit/tracking history would load PostgreSQL unnecessarily and add
latency to hot-path reads.

## Decision

Each database carries only its own area of responsibility:

| Technology | Role | Example data |
|---|---|---|
| PostgreSQL | Source of truth, ACID | users, orders, order_items, payments, refunds, wallet/loyalty/inventory transactions |
| MongoDB | Flexible document data | audit records, order event history, delivery tracking history, analytics documents |
| Redis | Hot data (not source of truth) | cache, session, rate limiting, OTP, courier's latest coordinate, order status cache |

MongoDB is never used as a replacement for PostgreSQL — money and balance operations live only
in PostgreSQL. If data in Redis is lost, the system must stay functional (only performance is
affected, no data loss) — this confirms Redis is always a "cache/hot cache", never the "single
source of truth".

## Reason

- PostgreSQL's transaction guarantees are irreplaceable for financial and order data that
  requires ACID.
- Audit/tracking history is large in volume, has a schema that can change frequently, and
  rarely needs complex JOINs — a document model (MongoDB) is a better fit and keeps
  unnecessary write load off PostgreSQL.
- "Only the latest value matters" data, such as a courier's latest coordinate or active order
  status, needs Redis's in-memory speed; the history of that data is kept in MongoDB.

## Consequences

- A cache invalidation and TTL policy must be documented (see `docs/database/`).
- Where each piece of data is stored is tracked via the Database Responsibility Matrix.
- Cross-service consistency is maintained via the event-driven mechanism (RabbitMQ + Outbox,
  see ADR 0001) — there is no direct cross-database transaction.

## Alternatives

- **PostgreSQL only (for everything):** rejected — unnecessary schema rigidity and write load
  for audit/tracking.
- **MongoDB only (for everything):** rejected — the lack of ACID guarantees is unacceptable
  for financial operations.
