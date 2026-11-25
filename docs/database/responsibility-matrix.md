# Database Responsibility Matrix

Operationalizes [ADR 0002](../adr/0002-polyglot-persistence-postgresql-mongodb-redis.md)'s
categorical role split (PostgreSQL = source of truth/ACID, MongoDB = flexible document data,
Redis = hot/non-authoritative data) into a concrete mapping for every entity named in master
prompt §6 and §11, so Phase 6+ implementers do not have to re-derive it per module.

## PostgreSQL — source of truth, ACID

| Entity | Reason |
|---|---|
| users | Identity/credentials; requires strict consistency and is the anchor for every role assignment in ADR 0006. |
| customers | Profile data referenced by orders and payments; needs relational integrity with those tables. |
| addresses | Structured, relational to a customer; referenced by orders for delivery — not document-shaped data. |
| branches | Structured entity referenced by orders, inventory, and staff role scope (ADR 0006); low write volume. |
| restaurants | Structured parent entity of branches; same relational reasoning. |
| products | Structured, referenced by pricing, cart, and orders; core fields need relational joins for checkout totals. |
| menu items | Structured, joined against products/pricing/availability at order time — core fields stay relational; variable extras live in MongoDB as flexible product metadata (below). |
| pricing / promotions | Order totals are computed server-side only (master prompt §11) by a centralized pricing engine — this calculation cannot tolerate eventual consistency. |
| orders | Financial/ACID record; the authoritative state machine (master prompt §11) lives here. |
| order_items | Financial/ACID, same transaction boundary as orders. |
| payments | Financial/ACID; money is Decimal/minor units, never float (CLAUDE.md hard rule). |
| refunds | Financial/ACID, same boundary as payments. |
| wallet transactions | Financial ledger entry; master prompt §6 explicitly assigns wallet/loyalty/inventory transactions to PostgreSQL. |
| loyalty transactions | Financial/point ledger entry — same explicit assignment as wallet transactions. |
| inventory transactions | Stock-movement ledger entry — same explicit assignment; feeds `InventoryUpdated` (ADR 0005) but the ledger itself is ACID. |

## MongoDB — flexible document data

| Entity | Reason |
|---|---|
| audit records | High write volume, schema that evolves per event type, rarely needs relational JOINs — explicitly assigned to MongoDB by ADR 0002. |
| order event history | The durable record Event Replay (ADR 0005) reads from; append-only, variable shape per event type. |
| delivery tracking history | High-frequency GPS history; Redis holds only the *latest* coordinate (below) — history is MongoDB's explicit role per ADR 0002 and master prompt §6. |
| recommendation history | Document-shaped, explicitly assigned to MongoDB by ADR 0002; feeds the AI Pizza Recommendation feature without touching transactional tables. |
| analytics documents | Explicitly assigned to MongoDB by ADR 0002; aggregation-heavy, schema-flexible. |
| notification history | Delivery/retry/tracking record per notification (master prompt §6) — variable shape per channel (push/email/SMS/in-app), not relational. |
| flexible product metadata | Variable, per-product extra detail (e.g. nutritional/allergen detail, imagery variants) that does not need relational joins — explicitly assigned to MongoDB by ADR 0002, complementing the relational core fields in `products`/`menu items` above. |

## Redis — hot data, never the source of truth

| Entity | Reason |
|---|---|
| cart (temporary checkout) | Pre-checkout working state; losing it only inconveniences the customer (re-add items), it is never a financial record — promoted to PostgreSQL `orders`/`order_items` only once checkout succeeds. |
| cache entries (incl. menu cache) | Generic read-through cache over PostgreSQL data (e.g. menu listings); Redis is explicitly "not source of truth" per ADR 0002, PostgreSQL stays authoritative. |
| sessions | Short-lived session-state cache for fast lookup. The *authoritative* session/refresh-token record is `refresh_tokens` in PostgreSQL per ADR 0006 — this Redis entry mirrors it for speed, it is not itself the source of truth. |
| rate-limit counters | Self-expiring counters (login/refresh/OTP-request throttling per ADR 0006) — by definition hot, short-lived, and never needed after their window closes. |
| OTP codes | Must expire by design (a non-expiring OTP is a security defect, see Security Requirements) — Redis's TTL is the enforcement mechanism, not just an optimization. |
| courier's latest coordinate | Only the *latest* value matters for live tracking; the history of the same data is explicitly MongoDB's role (ADR 0002, master prompt §6). |
| order status cache | Read-heavy during active delivery (customer polling); PostgreSQL's `orders` row stays authoritative, this cache only avoids hitting it on every poll. |

See [redis-caching-and-ttl-policy.md](redis-caching-and-ttl-policy.md) for the TTL and
invalidation rule for every Redis-held entity in this table.
