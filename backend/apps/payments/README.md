# Payments

Owns payment capture for an `Order` (Issue #198): confirms a Phase 11 `Order` from
`PENDING_PAYMENT` into `CONFIRMED` (gateway success) or `PAYMENT_FAILED` (gateway failure),
behind a provider-agnostic gateway abstraction. `Payment` is one row per capture attempt.

## Scope boundaries (deliberately out of this Task)

- **A real online PSP integration** (Stripe, etc.) is not part of this Task -- only
  `cash_on_delivery` and an in-process `mock_online` simulation gateway exist today. Wiring a
  real provider's SDK/credentials behind `PaymentGateway` is future work and, per the Issue's
  own Business Context, requires explicit human confirmation before any provider credential or
  provider-specific config is added to this repository -- never assume authorization to do
  that from this Task alone.
- **Refunds** (`refund()` exists on every gateway here but has no API caller yet) are Issue
  #200's job.
- **Wallet balance / store credit** was Issue #199's job -- see `backend/apps/wallet/README.md`.
  It registers a third gateway, `WalletGateway`, into `domain/gateway_registry.py` at Django
  startup via `register_gateway()`, without `apps.payments` ever importing `apps.wallet`
  (ADR 0004 one-way dependency direction; see that README for the full
  `AppConfig.ready()`-based registration mechanism).
- **Multi-currency** does not exist anywhere else in this codebase (`Order`/`Branch`/`Product`
  all store a bare `Decimal`, no currency field) -- this Task fixes a single implicit
  `DEFAULT_CURRENCY = "USD"` (`services/payment_service.py`), documented there as revisit-if-
  multi-currency-becomes-required, same "decide the ambiguous bit, document it" pattern as
  Issue #196's branch-switch decision.

## Gateway abstraction design

`domain/gateway.py` defines `PaymentGateway` (ABC): `authorize(amount, currency,
payment_method_token, idempotency_key, customer_id)`, `capture(authorization_id, amount)`,
`refund(capture_id, amount, customer_id)`, each returning a frozen result dataclass
(`AuthorizationResult`/`CaptureResult`/`RefundResult`) carrying `success`, a provider-side id,
an opaque `provider_reference`, and an optional `failure_reason`.

This shape was researched against a mainstream PSP's current manual-capture lifecycle
(Stripe's PaymentIntents: `authorize` places a hold, `capture` settles up to the authorized
amount, `refund` reverses money already captured -- see Stripe's
["Place a hold on a payment method"](https://docs.stripe.com/payments/place-a-hold-on-a-payment-method)
guide, checked at implementation time per the repository's research-before-implementing rule)
and confirms the Issue's own prescribed `authorize/capture/refund` interface was already the
industry-standard shape.
Chosen so that adding a real provider later only means registering one new concrete class into
`domain/gateway_registry.py`, never a change to this interface or to `PaymentService`.

Two gateways exist today, both in `domain/`, consistent with ADR 0004's fixed per-module
layout (confirmed against every other module's directory structure) and with the precedent
that pure, Django-free domain logic belongs in `domain/`:

- `CashOnDeliveryGateway` -- cash is collected physically later, outside this system's
  accounting until Issue #199's reconciliation; `authorize`/`capture`/`refund` are all
  immediate, unconditional successes. `payment_method_token` is ignored.
- `MockOnlineGateway` -- simulates a real online PSP's authorize -> capture flow in-process,
  no real network call. Outcome is deterministic and token-driven, the same magic-test-token
  convention every mainstream PSP sandbox uses: a token exactly equal to `DECLINE_TOKEN =
  "tok_decline"` always fails authorization (`card_declined`); a missing/empty token fails with
  `missing_payment_method_token`; any other non-empty token succeeds.

`domain/gateway_registry.py::get_gateway(payment_method)` looks a gateway up by
`PaymentMethod` value, raising `UnknownPaymentMethodError` for anything unregistered.
`register_gateway(payment_method, gateway)` (added by Issue #199) lets another module add a
gateway to this registry without this module ever importing that other module back -- its only
caller today is `apps.wallet.apps.WalletConfig.ready()`.

`customer_id` on `authorize()`/`refund()` was added by Issue #199: `WalletGateway` must know
whose wallet to debit/credit, and no other value already flowing through
`PaymentService.capture_for_order()` identified the customer to a gateway implementation.
`CashOnDeliveryGateway`/`MockOnlineGateway` accept and ignore it, the same way they already
ignored `payment_method_token` where it doesn't apply.

## Security Requirements

No card data (PAN/CVV/expiry) field exists anywhere in this module. `payment_method_token` is
treated as an already-opaque, pre-tokenized string (as if tokenized client-side by a real PSP's
JS SDK) -- it is never parsed, validated as a card number, or logged. Confirmed by grepping
this module for card-data field names (`card_number`, `cvv`, `cvc`, `expiry`, `pan`, etc.);
the only matches are this design note and the equivalent docstring comments in
`models/payment.py` and `domain/mock_online_gateway.py`.

## `PaymentService.capture_for_order()`

1. Resolves the `Order` by ownership via `apps.orders.services.order_service.OrderService
   .get_owned()` and checks it is still `OrderStatus.PENDING_PAYMENT` --
   `OrderNotPendingPaymentError` otherwise.
2. Looks up the gateway via the registry, authorizes then immediately captures the full order
   total in one call (no partial-capture use case exists in this Task).
3. The gateway calls happen **before** the DB transaction opens: they represent a (simulated)
   external effect that a DB rollback could never undo. Only the local `Payment` row write and
   the `Order` transition are wrapped together in `transaction.atomic()`.
4. On success, transitions the `Order` to `CONFIRMED` and publishes `PaymentCompleted`; on
   failure, transitions it to `PAYMENT_FAILED` (carrying the gateway's `failure_reason`) and
   publishes `PaymentFailed`. Either way a `Payment` row is created -- a declined payment is a
   legitimate, successfully-recorded outcome, not an application error, matching how a real PSP
   returns `200` with a Charge/PaymentIntent object whose own `status` reflects the decline.

### Idempotent-handler side-effect ordering

`OrderNotPendingPaymentError` is checked **inside** `capture_for_order()`, which
`PaymentCaptureView` only ever calls from inside the handler closure passed to
`IdempotentActionMixin.perform_idempotent()` -- never before it. A duplicate capture request
carrying the same `Idempotency-Key` must replay the first request's cached response without
re-running this check against the order's now-`CONFIRMED` post-capture state; this is the exact
lesson Issue #197's checkout-replay bug taught (see `apps/orders/api/views.py::CheckoutView`
and the project's own memory on idempotent-handler side-effect ordering). By contrast, the
order *ownership* check in `PaymentCaptureView.post()` runs before `perform_idempotent()` is
called -- ownership never changes as a result of capturing a payment, so re-running it on a
replay is harmless.

## Layout (ADR 0004)

`repositories/payment_repository.py` is the only file issuing ORM queries for `Payment`.
`PaymentOutboxEvent` rows are created directly from `PaymentService` (same convention as
`apps.orders.services.order_service` -> `OrderOutboxEvent`), not through the repository.

`payments` depends on `apps.orders.services.order_service.OrderService` (ownership lookup and
status transition) and on the pure, Django-free `apps.orders.domain.state_machine.OrderStatus`
enum -- a cross-module `domain/`-only import, already precedented by
`apps.customers.services.verification_service` importing
`apps.identity.domain.rbac.RoleCode`. `payments` never imports `apps.orders.models` or
`apps.orders.repositories` directly (ADR 0004).

`Payment.order_id` is a plain field, not a cross-app FK, same pattern as `Order.customer_id` --
ownership/cascade is enforced at the service layer, never the DB layer.

## Authorization

`IsAuthenticated` only -- the acting customer is resolved from `request.user` via
`ProfileService.get_profile()`, never from a client-supplied id (same pattern as
`apps.orders.api.views._customer_id_for`). An order id that exists but belongs to a different
customer returns `404`, never `403` (same pattern as `apps.orders.api.views.CheckoutView`).

## `api/` endpoints

- `POST /api/v1/payments/` -- `order_id`, `payment_method`, and (only for `mock_online`)
  `payment_method_token` in the body; mandatory `Idempotency-Key` header. `201` with the
  created `Payment` (`status: captured` or `status: failed`), or the first response, replayed,
  on a duplicate key. `400` for a missing header, an unknown/mismatched `payment_method_token`
  requirement, or an order that is not awaiting payment; `404` for an order not owned by this
  customer.

Publishes: `PaymentCompleted` (`payments.events` / `payment.completed.v1`) on a successful
capture; `PaymentFailed` (`payments.events` / `payment.failed.v1`) on a declined/failed
capture.
