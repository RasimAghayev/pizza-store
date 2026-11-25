# Domain Risk Register and Technical Debt Assessment

## Status

Accepted

## Purpose

This register names concrete technical and business risks for the Pizza Store Platform before
implementation begins, per the master prompt's Architecture-before-Business ordering (§1). It
takes ADR 0001 (Modular Monolith + EDA) and ADR 0002 (PostgreSQL/MongoDB/Redis split) as given
and focuses on risks that sit on top of those decisions. Each risk is cross-referenced to the
Phase expected to address or re-evaluate it, so later Phases make informed trade-offs instead
of discovering these risks mid-implementation.

## Risk Register

| # | Area | Risk | Likelihood | Impact | Mitigation / Deferred To |
|---|---|---|---|---|---|
| 1 | Order state machine | Concurrent status transitions (e.g. kitchen marks `preparing` while customer cancels) or double-submission from a retried client request corrupt the order state machine. | Medium | High | Enforce transitions via an explicit state machine with DB-level optimistic locking (`version` column) and idempotency keys on write endpoints. Deferred to Phase 6 (Backend Foundation) for the state machine implementation; Phase 7 validates via E2E tests. |
| 2 | Payments | Payment idempotency and reconciliation with an external gateway fails on network timeouts — a charge succeeds at the gateway but the local write is lost or duplicated. | Medium | High | Transactional Outbox (ADR 0001) plus a gateway idempotency key per order attempt; a reconciliation job cross-checks gateway status against local payment records. Deferred to Phase 6 (Payment module) and Phase 9 (Observability) for reconciliation job monitoring. |
| 3 | Multi-branch isolation | A manager or staff account for one branch can read or mutate another branch's orders, inventory, or reports due to a missing tenant filter. | Medium | High | Branch scoping enforced at the repository/query layer (not only in views), covered by dedicated authorization tests per endpoint. Deferred to Phase 6 (Backend Foundation, Repository Pattern) and Phase 10 (Security Hardening) for authorization test coverage. |
| 4 | Inventory | Two branches (or two concurrent orders in the same branch) decrement the same shared ingredient SKU simultaneously, causing oversold stock or negative inventory. | High | Medium | Row-level locking (`SELECT ... FOR UPDATE`) or atomic DB-level decrement with a non-negative constraint; reconcile via inventory transaction log. Deferred to Phase 6 (Inventory module). |
| 5 | Location/GPS data | Courier GPS coordinates and customer delivery addresses are collected without a documented retention/consent policy, creating a privacy and regulatory exposure. | Medium | High | Store live coordinates in Redis only (ADR 0002, hot/ephemeral), persist historical tracking in MongoDB with an explicit TTL/retention policy and consent capture at account creation. Deferred to Phase 1 (this task's companion, Issue #31 — Redis TTL policy) and Phase 10 (Security/Privacy). |
| 6 | Messaging | RabbitMQ message loss (broker restart before ack) or duplicate delivery (consumer crash after processing, before ack) causes missed or double-processed domain events. | Medium | High | Transactional Outbox for publish-side guarantees (ADR 0001); idempotent consumers keyed on event ID for consume-side guarantees; dead-letter queue for poison messages. Deferred to Phase 1 (ADR 0005 — Event topology, Issue #27) and Phase 6/7 for implementation. |
| 7 | Synthetic data | The synthetic dataset (§10 of the master prompt) is unrealistic (e.g. uniform order timing, no regional demand spikes), so performance and scaling decisions made against it don't hold under real production load patterns. | Medium | Medium | Model synthetic data generation on publicly documented restaurant-industry demand patterns (lunch/dinner peaks, weekend spikes); re-validate assumptions against real data once available post-launch. Deferred to Phase 5 (Data/Seeding) for generation, Phase 11 (Performance/Load Testing) for validation. |
| 8 | Local environment parity | Docker Compose (local/dev) behaves differently from the eventual VPS/Swarm/Kubernetes target (networking, resource limits, multi-node message ordering), so issues surface only after Phase 8 deployment. | Medium | Medium | Keep Compose service definitions as close as possible to the Swarm/K8s manifests (shared env var names, same images); validate early with a staging deploy rather than waiting until the end of Phase 8. Deferred to Phase 8 (Deployment) per ADR 0007 (Issue #29). |
| 9 | Courier assignment | Two couriers are assigned to the same order (race condition on "claim this delivery"), or no courier is available and the order silently stalls with no escalation. | Low | Medium | Atomic claim operation (conditional update, "assign if unassigned") plus a timeout/escalation event if no courier claims within an SLA window. Deferred to Phase 6 (Delivery/Courier module). |
| 10 | Pricing/promotions | Concurrent promotion or price-rule changes applied mid-cart or mid-checkout produce an order total that doesn't match what the customer saw. | Low | Medium | Price snapshot captured at cart checkout time, not recomputed from live rules at payment time; mismatches are surfaced for manual review rather than silently charged. Deferred to Phase 6 (Pricing/Cart module). |

## Likely Technical Debt

1. **Payment Gateway Abstraction with no real provider.** Phase 6 ships a Payment Gateway
   Abstraction with a single (sandbox/mock) implementation behind the interface; no real
   provider (Stripe, PayPal, local acquirer) is wired in. Swapping in a real provider later is
   a `type:security` + production-credential change requiring human confirmation per
   `CLAUDE.md`'s real-world-actions rule.
2. **No real notification provider.** Email/SMS/push notifications are modeled as domain
   events and logged/mocked rather than sent through a real provider (SendGrid, Twilio, FCM)
   until a provider is explicitly chosen and credentials provisioned.
3. **Single-region deployment target.** ADR 0007 picks one deployment target
   (VPS/Swarm/Kubernetes) for Phase 8; multi-region or multi-cloud failover is explicitly out
   of scope and would require a new ADR if real geographic redundancy becomes a requirement.
4. **Synthetic dataset stands in for production telemetry.** Capacity planning, index choices,
   and cache TTLs (Issue #31) are tuned against synthetic data (risk #7 above) until real
   traffic is observed; these are expected to need revisiting post-launch, not treated as final.
5. **Native mobile app deferred.** Only a PWA is built (per the technology stack); a native
   iOS/Android app is explicitly deferred and would need its own ADR and Phase if required
   later — the PWA's offline/push capabilities are a known, accepted limitation until then.

## References

- ADR 0001: Modular Monolith + Event-Driven Architecture
- ADR 0002: Polyglot Persistence — PostgreSQL, MongoDB, Redis
- ADR 0005 (Issue #27): Event topology and Outbox design
- ADR 0007 (Issue #29): Deployment target priority
- Issue #31: Database responsibility matrix and Redis TTL policy
