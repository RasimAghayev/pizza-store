# ADR 0005: Event Topology and Outbox Design

## Status

Accepted

## Context

ADR 0001 fixed Event-Driven Architecture via RabbitMQ as the cross-module communication
mechanism for the modular monolith, and made the Transactional Outbox Pattern and idempotent
consumers mandatory consequences. Master prompt §6 lists the required EDA capabilities (naming
convention, schema versioning, exchange/queue/routing key structure, durable queues, publisher
confirms, message ack, retry policy, Dead Letter Queue, Transactional Outbox, idempotent
consumers, Event Replay, correlation ID, distributed tracing) and the set of core domain events
(`CustomerRegistered`, `CustomerBirthday`, `OrderCreated`, `OrderConfirmed`,
`PaymentCompleted`, `PaymentFailed`, `OrderAccepted`, `OrderPreparing`, `OrderReady`,
`CourierAssigned`, `DeliveryStarted`, `CourierLocationUpdated`, `OrderDelivered`,
`OrderCancelled`, `RefundRequested`, `RefundCompleted`, `InventoryUpdated`,
`LoyaltyPointsAdded`, `CampaignActivated`), but leaves every concrete naming and schema
decision open.

Without fixing this once, up front, Phase 6 (Backend Foundation, which builds the Outbox and
consumer infrastructure itself) and every later phase that publishes or consumes an event would
each invent their own exchange names, routing key formats, and envelope shapes, making the
messaging layer inconsistent across modules and impossible to document centrally.

No backend code exists yet; this ADR is written purely from ADR 0001, ADR 0002 (MongoDB holds
order event history — the durable store Event Replay reads from), and master prompt §6.

## Decision

### Exchange and queue topology

One durable **topic exchange per publishing bounded-context module**, named `<module>.events`,
where `<module>` matches the Django app name from ADR 0001's module list. Only the owning
module's publisher ever publishes to its own exchange. This ADR's event set requires eight
exchanges: `customers.events`, `orders.events`, `payments.events`, `kitchen.events`,
`couriers.events`, `delivery.events`, `inventory.events`, `loyalty.events`.

A single shared `domain-events` exchange for every event type was considered and rejected (see
Alternatives) in favor of one exchange per module, which keeps publish-side ownership aligned
with bounded-context isolation.

Each consumer declares its **own durable queue** per event type it cares about — queues are
never shared between consumers, so one slow or failing consumer cannot block another. Queue
naming: `<consumer-module>.<routing-key-with-dots-as-dashes>.q`, bound to the owning module's
exchange with the exact routing key. Example: the `notifications` module consuming
`order.created.v1` from `orders.events` declares `notifications.order-created-v1.q`.

All exchanges and queues are declared `durable`. Publishers use **publisher confirms**
(`confirm_delivery`) and only mark an Outbox row published after the broker acks it. Consumers
use **manual acknowledgement** (`ack` only after the handler's DB transaction, including the
idempotency record from the section below, commits) with a bounded `prefetch_count` per
consumer so one connection cannot buffer unbounded unacked messages.

### Routing key convention

`<aggregate>.<event-verb>.v<schema_version>`, all lower\_snake\_case, e.g. `order.created.v1`,
`payment.completed.v1`, `courier.location_updated.v1`. The aggregate noun matches the subject
of the event name (not necessarily the publishing module — e.g. `OrderAccepted` is published by
`kitchen` but routes as `order.accepted.v1`, since the event is still about the Order aggregate's
state as observed by the kitchen module). `v<n>` is a literal, integer-only suffix; it is part
of the routing key (not just the envelope) so a consumer can bind to a specific version without
receiving others during a migration window.

### Event envelope and schema versioning

Every event, regardless of type, uses the same envelope:

```json
{
  "event_id": "f0b8c2de-...-uuid4",
  "event_type": "order.created",
  "schema_version": 1,
  "occurred_at": "2026-11-25T14:03:11.482Z",
  "correlation_id": "a1e4...-uuid4",
  "causation_id": "7c2d...-uuid4",
  "producer": "orders",
  "payload": { "...": "event-specific fields" }
}
```

- `event_type` is the routing key without the version suffix.
- `schema_version` is an integer, scoped per `event_type` (not a global counter).
- `correlation_id` ties together every event/command/HTTP call belonging to one end-to-end
  business transaction (e.g. one customer checkout). It is generated once, as a UUID, at the
  first edge request (API gateway / view) and propagated through the service layer, into the
  Outbox row, into the envelope, and into any outbound HTTP/log call the handler makes.
- `causation_id` names the specific event or command that directly caused this one (distinct
  from `correlation_id`, which spans the whole transaction, not just the immediate parent). Null
  for the first event in a chain.
- A breaking payload change bumps `schema_version` and the routing key's `v<n>` suffix; the
  producer dual-publishes the old and new version until every consumer has migrated, then retires
  the old version in a follow-up change. A consumer that receives a `schema_version` it does not
  recognize **never silently drops or guesses** — it nacks into its retry/DLQ path (see below)
  and logs the envelope's non-payload fields so the mismatch is visible, instead of crashing the
  whole consumer process or corrupting state by misreading the payload.

### Transactional Outbox

Each publishing module owns an `outbox_events` table (same database/transaction as its business
tables, per module, consistent with ADR 0001's module isolation):

| Column | Purpose |
|---|---|
| `id` | UUID primary key; becomes the envelope's `event_id`. |
| `aggregate_type`, `aggregate_id` | Which domain object this event is about. |
| `event_type`, `schema_version` | As above. |
| `payload` | JSONB, the envelope's `payload`. |
| `correlation_id`, `causation_id` | As above. |
| `created_at` | When the business transaction produced the row. |
| `status` | `pending` / `published` / `failed`. |
| `attempts`, `last_error`, `published_at` | Publisher bookkeeping. |

The business transaction (e.g. creating an order) inserts its domain rows and the corresponding
`outbox_events` row **in the same database transaction** — so the event is guaranteed to exist
if and only if the business change committed. A separate background publisher process polls
`outbox_events WHERE status = 'pending' ORDER BY created_at FOR UPDATE SKIP LOCKED`, publishes
each row to its module's exchange with publisher confirms, and only then updates it to
`published`. If RabbitMQ is unreachable or the confirm times out, the row is left `pending` (with
`attempts`/`last_error` updated) and retried on the next poll — this is what guarantees
at-least-once delivery even across a broker outage, per ADR 0001's consequence and master
prompt §6's explicit requirement that a committed PostgreSQL transaction must never lose its
event just because RabbitMQ was briefly unreachable.

### Idempotent consumers

Each consuming module owns a `processed_events` table: `(event_id UUID, consumer_name TEXT,
processed_at TIMESTAMPTZ)`, with a unique constraint on `(event_id, consumer_name)`. A consumer
handler, in one DB transaction, attempts an `INSERT ... ON CONFLICT (event_id, consumer_name) DO
NOTHING` into `processed_events` *and* performs the business side effect (e.g. recording a
payment as settled); if the insert reports a conflict, the handler already ran for this event
and the message is simply acked without repeating the side effect. This is what satisfies
master prompt §6's hard requirement that a redelivered event must never cause a payment or order
operation to execute twice.

### DLQ and retry policy

A failed handler (business exception, or a `schema_version` it cannot process) does not retry
in a tight loop against the live queue. Instead, each queue `<q>` has a companion retry queue
`<q>.retry` with a per-message TTL and its dead-letter-exchange pointing back at `<q>`'s binding
— the standard RabbitMQ delayed-retry pattern, since RabbitMQ queues have no native delayed
redelivery. Backoff schedule: 3 attempts at 30s, 2m, then 10m. After the 3rd failure, the message
is routed to `<q>.dlq` instead of `<q>.retry`, where it is held for manual inspection (tooling
and the alert that fires when a DLQ's depth exceeds zero are Phase 5 observability /
Phase 6+ work; this ADR fixes only the queue shape and backoff numbers, not the tooling).

### Event Replay

RabbitMQ queues are transient delivery channels, not a replay log — once a message is acked it
is gone. The durable, replayable record is the **order event history collection already assigned
to MongoDB by ADR 0002**, plus each module's `outbox_events` table kept as an append-only
archive (rows are never deleted, only marked `published`). A future replay tool re-publishes
selected historical envelopes from these stores back onto the normal exchanges, so consumers
process them through the exact same idempotent path as a live event — replay is a producer-side
operation, not a special consumer code path. Building that tool is Phase 6+ work; this ADR fixes
where its source data lives.

### PII and correlation IDs

`correlation_id` and `causation_id` are opaque, randomly generated UUIDs that carry no customer
data by construction. They must never be used as a backdoor to smuggle PII into logs: a log line
may include the envelope's `correlation_id`, `event_type`, and `event_id`, but logging the
`payload` wholesale is forbidden wherever it contains customer-identifying fields (name, address,
phone, GPS) — only explicitly allow-listed, non-PII payload fields may be logged. The concrete
allow-list and redaction mechanism belong to ADR 0006 (security baseline); this ADR only fixes
the constraint so Phase 6 does not build a logging path that leaks PII through the event pipeline
by default.

### Event catalog

Every event from master prompt §6, with its owning module, exchange, and routing key, is listed
in `docs/messaging/event-catalog.md`.

## Reason

- Fixing exchange/queue/routing-key naming once, before Phase 6 writes the first publisher,
  means every module's event infrastructure looks the same instead of eighteen ad hoc
  conventions.
- The Outbox and idempotency table designs are described here at the column/transaction level
  (not just "use the Outbox pattern") so Phase 6 can implement them directly without a second
  design pass, and so every module's Outbox/idempotency tables are structurally identical and
  reviewable against one shape.
- Tying Event Replay to the MongoDB order event history (ADR 0002) rather than inventing a new
  store avoids a third persistence decision for the same data.

## Consequences

- Phase 6's event infrastructure work (building the Outbox publisher, the idempotent-consumer
  base class, and the retry/DLQ queue declarations) implements exactly this design rather than
  choosing its own.
- Every new event added after this ADR must get a routing key following this convention and an
  entry in `docs/messaging/event-catalog.md` before Phase 6+ code publishes it.
- A schema change to an existing event requires a version bump and a dual-publish migration
  window, never an in-place payload change under the same `schema_version`.

## Alternatives

- **One exchange per event type** (19 exchanges instead of 8): rejected — a topic exchange
  already lets consumers bind selectively via routing key patterns, so per-event-type exchanges
  would only multiply broker objects to manage without adding any routing capability.
- **One shared `domain-events` exchange for the whole platform**: rejected — it would blur
  which module is allowed to publish what, undermining the bounded-context publish ownership
  that ADR 0001's module isolation depends on.
- **Immediate nack-and-requeue retry (no separate retry queue)**: rejected — redelivering
  instantly in a tight loop wastes broker and consumer resources on a failure that is unlikely to
  resolve within milliseconds, and gives no backoff window for a transient dependency (e.g. a
  downstream HTTP call) to recover.
- **A global auto-incrementing `schema_version`** shared across all event types: rejected — it
  would force every event's version counter to advance whenever any event anywhere changed,
  making the number meaningless as a per-event compatibility signal.
