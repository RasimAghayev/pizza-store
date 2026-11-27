# Event Catalog

Every domain event from master prompt §6, with its owning module, exchange, and routing key,
per [ADR 0005](../adr/0005-event-topology-and-outbox-design.md). This table is the single
source of truth for routing keys — a new event is added here before any publisher/consumer
code for it is written (Phase 6+).

All routing keys follow `<aggregate>.<event-verb>.v<schema_version>`. All exchanges are durable
topic exchanges named `<module>.events`.

**Infrastructure status (2026-11-26, Issue #130):** the generic Transactional Outbox
publisher and idempotent-consumer base classes now exist in `backend/shared/events/` and are
proven against a real RabbitMQ broker. Seven of the eight exchanges and eighteen of the
nineteen events below are still naming reservations, not live exchanges/queues -- the first
real module to publish one of these events is what actually creates its exchange and appends
a true catalog entry; the test fixture event used to prove the Outbox/idempotent-consumer
plumbing is deliberately not listed here, since it is not a real domain event.

**Live (2026-11-27, Issue #176):** `CustomerRegistered` / `customers.events` /
`customer.registered.v1` -- published by `apps.customers.services.registration_service
.RegistrationService.register()` on every customer sign-up, proven end-to-end against a real
RabbitMQ queue by `backend/apps/customers/tests/integration/test_customer_registered_event.py`.

| Event | Owning module | Exchange | Routing key |
|---|---|---|---|
| CustomerRegistered | customers | `customers.events` | `customer.registered.v1` |
| CustomerBirthday | customers | `customers.events` | `customer.birthday.v1` |
| OrderCreated | orders | `orders.events` | `order.created.v1` |
| OrderConfirmed | orders | `orders.events` | `order.confirmed.v1` |
| PaymentCompleted | payments | `payments.events` | `payment.completed.v1` |
| PaymentFailed | payments | `payments.events` | `payment.failed.v1` |
| OrderAccepted | kitchen | `kitchen.events` | `order.accepted.v1` |
| OrderPreparing | kitchen | `kitchen.events` | `order.preparing.v1` |
| OrderReady | kitchen | `kitchen.events` | `order.ready.v1` |
| CourierAssigned | couriers | `couriers.events` | `courier.assigned.v1` |
| DeliveryStarted | delivery | `delivery.events` | `delivery.started.v1` |
| CourierLocationUpdated | delivery | `delivery.events` | `courier.location_updated.v1` |
| OrderDelivered | delivery | `delivery.events` | `order.delivered.v1` |
| OrderCancelled | orders | `orders.events` | `order.cancelled.v1` |
| RefundRequested | payments | `payments.events` | `refund.requested.v1` |
| RefundCompleted | payments | `payments.events` | `refund.completed.v1` |
| InventoryUpdated | inventory | `inventory.events` | `inventory.updated.v1` |
| LoyaltyPointsAdded | loyalty | `loyalty.events` | `loyalty.points_added.v1` |
| CampaignActivated | loyalty | `loyalty.events` | `campaign.activated.v1` |

Notes:

- `OrderAccepted`/`OrderPreparing`/`OrderReady` are published by `kitchen`, not `orders` — the
  event is still about the Order aggregate's state, but the module that observes and reports
  that transition is the kitchen, per ADR 0005's "aggregate names the subject, module names the
  observer" rule.
- `CourierLocationUpdated` is published by `delivery` (which owns GPS tracking), not `couriers`
  (which owns courier assignment/availability) — see master prompt §6's Delivery domain split.
- Adding a new event: append a row here, assign it the next unused routing key under its
  aggregate, and only then write the publisher. A breaking payload change to an existing event
  adds a new row with `v2` rather than editing the `v1` row in place, until the old version is
  retired per ADR 0005.
