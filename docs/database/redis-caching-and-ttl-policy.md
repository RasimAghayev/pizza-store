# Redis Caching and TTL Policy

Covers every Redis-held entity from the
[Database Responsibility Matrix](responsibility-matrix.md): its key pattern, TTL, and what
triggers its invalidation before that TTL expires. Per [ADR 0002](../adr/0002-polyglot-persistence-postgresql-mongodb-redis.md),
nothing here is ever the source of truth — if a key is lost, the system must stay correct
(only a cache miss or a forced re-authentication results, never incorrect business state).

## TTL table

| Entity | Key pattern | TTL | Invalidation trigger |
|---|---|---|---|
| Cart / temporary checkout | `cart:{customer_id}` | 24 hours | Deleted on successful checkout (promoted to PostgreSQL `orders`); TTL refreshes on every cart mutation so an active session never expires mid-use. |
| Menu cache (a `cache entries` instance) | `menu:{branch_id}` | 5 minutes | Explicitly deleted by the service layer in the same transaction that updates a product/price/availability record — short TTL is a safety net, not the primary invalidation path. |
| Generic cache entries (other read-through caches) | `cache:{resource}:{id}` | 5–15 minutes, resource-dependent | Explicit delete on the corresponding PostgreSQL write when the write path is known (invalidate-on-write); otherwise left to TTL expiry for low-value/rarely-changing data. |
| Session cache | `session:{user_id}:{jti}` | 15 minutes, matching the ADR 0006 access-token lifetime | Explicitly deleted on logout and on refresh-token-family revocation (ADR 0006's stolen-token response), keeping this mirror in sync with the authoritative `refresh_tokens` table in PostgreSQL. |
| Rate-limit counters | `ratelimit:{scope}:{identifier}` (`scope` = `login` / `refresh` / `otp-request` / etc.) | Matches the throttling window — 60 seconds for per-IP counters, 15 minutes for per-account lockout counters | None needed beyond TTL expiry — a fixed-window counter is self-cleaning by design. |
| OTP codes | `otp:{purpose}:{identifier}` | 5 minutes | Deleted immediately on successful verification (single-use), in addition to the 5-minute TTL — both the expiry and the explicit delete are required, since a verified OTP must never be replayable even within its TTL window. |
| Courier's latest coordinate | `courier:location:{courier_id}` | 2 minutes, refreshed on every GPS update | No explicit delete — natural expiry if a courier's app stops reporting is the intended signal (treated as "went offline/stale" by the delivery module), separate from the permanent history each update also writes to MongoDB via the `CourierLocationUpdated` event (ADR 0005). |
| Order status cache | `order:status:{order_id}` | 30 seconds | Explicitly invalidated on every order state-machine transition (master prompt §11's lifecycle) — the short TTL is a fallback only, not the primary mechanism, since customer-facing status must reflect a transition immediately, not after up to 30 seconds. |

## Cache invalidation strategy

Two patterns are used, chosen per entity above rather than one blanket rule:

- **Invalidate-on-write** (menu cache, order status cache, session cache, cart): the service
  layer that performs the PostgreSQL write also deletes or overwrites the corresponding Redis
  key, in the same request, immediately after the write commits. This is used wherever stale
  data would be user-visible and misleading (an order status that hasn't advanced, a menu price
  that hasn't updated) — the short TTL on these keys is a safety net for the rare case a
  service-layer invalidation is missed, not the primary mechanism.
- **TTL-only expiry** (rate-limit counters, generic low-value cache entries, courier location):
  used where the data is inherently short-lived by definition (a rate-limit window, a GPS
  coordinate only meaningful for the last couple of minutes) or where staleness has no
  meaningful user-facing cost significant enough to justify wiring an explicit invalidation
  path.
- **Write-through caching is deliberately not used anywhere in this policy**: every Redis key
  here is populated lazily (on first read, or on the event that creates the ephemeral state —
  e.g. an OTP request), not written synchronously alongside every PostgreSQL write regardless
  of whether it is ever read. Write-through would mean paying a Redis write cost on paths that
  may never be read from cache (e.g. a branch whose menu nobody requests before the next price
  change) for no benefit over populate-on-read.

A key with no TTL is not a valid state for any entry in the table above — every row either
expires on its own or is both explicitly invalidated and carries a TTL as a fallback.
