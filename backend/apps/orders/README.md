# Orders

Owns the order lifecycle state machine and the checkout flow that converts a customer's
Cart (Issue #196) into a real `Order` (Issue #197): `Order`, `OrderItem` (an immutable
snapshot of each cart line at checkout time), and `OrderStatusAudit` (one row per status
change, Postgres-only per ADR 0002).

## Scope boundaries (deliberately out of this Task)

- **Payment** (confirming `PENDING_PAYMENT` into `CONFIRMED`, or `PAYMENT_FAILED`) is Issue
  #198's job -- this Task only ever creates an `Order` in `PENDING_PAYMENT`.
- **Kitchen/delivery** (`ACCEPTED` through `DELIVERED`) is Phase 12's job.
- **Refunds** (`CANCELLED`/`DELIVERED` -> `REFUND_PENDING` -> `REFUNDED`) are Issue #200's
  job.
- **Discounts/campaigns** are Phase 13's job -- `Order.discount_amount` exists now (always
  `0.00` here) purely so that Task doesn't need a schema migration to add the column.

## State machine design

`domain/state_machine.py` is a pure, Django-import-free module (ADR 0004 style, matching
`apps/products/domain/pricing.py`/`apps/menu/domain/availability.py`): `OrderStatus` (a
Django-free `StrEnum`, reused by `Order.status`'s `choices=` the same way
`apps.identity.domain.rbac.RoleCode` is reused by `RoleAssignment.role_code`), an explicit
`TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]]` table, and `next_status()` -- returns
the target status on a legal edge, raises `IllegalOrderTransitionError` otherwise.

The master prompt/Issue #197 name every lifecycle *node* but not every *edge*; this Task
settles the ambiguous ones itself (same pattern as Issue #196's branch-switch decision),
documented in the module's own docstring:

- `CANCELLED` is reachable from every active, non-terminal, pre-`DELIVERED` status, not just
  `PENDING_PAYMENT` -- an order can be aborted at any stage before it reaches the customer.
- `PAYMENT_FAILED` can transition back to `PENDING_PAYMENT` (a client-initiated payment
  retry) in addition to `CANCELLED` (giving up).
- `REFUND_PENDING` is reachable only from `CANCELLED` and `DELIVERED`, matching Issue #200's
  own explicit design -- a refund reverses money already captured for an order that has
  stopped moving forward; it is not itself how an in-flight order gets stopped.

The `ACCEPTED` -> ... -> `DELIVERED` edges are included in the table for Phase 12 to drive
via `OrderService.transition()`, but **no endpoint in this Task reaches them** -- the only
production caller of `transition()` today is internal test coverage proving the mechanism
works; Issue #198 (payment) is the first real caller (`PENDING_PAYMENT` -> `CONFIRMED` /
`PAYMENT_FAILED`).

## Checkout flow

`OrderService.checkout(customer_id, cart_id, address_id, idempotency_key)`:

1. Re-resolves the customer's own active cart server-side (`CartService.get_active_cart`)
   and rejects if it doesn't match `cart_id` or has no items -- `cart_id` is never trusted on
   its own (Security Requirements).
2. Re-prices every line through `CartService.price_cart()` (itself a fresh
   `PricingService.quote()` call per line) -- never the cart's stored
   `unit_price_snapshot`.
3. Enforces the branch's `minimum_order_amount` against the food subtotal (excluding
   `delivery_fee`).
4. Resolves the chosen `Address` by ownership and copies its fields onto the `Order` as a
   one-time snapshot (`delivery_street_and_unit`/`delivery_city`/...) -- never a live FK, so
   a later address edit/delete can't retroactively change an already-placed order.
5. In one DB transaction: creates `Order` (`status=PENDING_PAYMENT`), `OrderItem` rows (one
   per cart line; a half-and-half line's `name` combines both products' names), the initial
   `OrderStatusAudit` row (`from_status=None` -- creating an order is not itself a state
   *transition*), clears the cart, and publishes `OrderCreated`.

`subtotal`/`delivery_fee`/`total_amount` are always server-computed; the checkout request
serializer (`CheckoutRequestSerializer`) accepts only `address_id` -- there is no
amount/total field for a client to even tamper with.

Duplicate-submission protection is a DRF-layer concern, not `OrderService`'s: `CheckoutView`
makes the `Idempotency-Key` header **mandatory** (rejecting with no header before even
calling `IdempotentActionMixin.perform_idempotent`, unlike that mixin's own
per-view-optional default) and wraps the whole checkout in `shared/idempotency`
(Issue #195) -- a retried request with the same key and body replays the first response
verbatim instead of creating a second `Order`. `idempotency_key` is still passed into
`OrderService.checkout()` and stored on the `Order` row, but only for traceability.

`OrderService.transition(order_id, to_status, reason)` is the generic entry point every
later status change goes through: checks the edge against `TRANSITIONS`, updates `Order
.status`, and inserts one `OrderStatusAudit` row, all in one transaction. Publishes
`OrderConfirmed` only when `to_status` is `CONFIRMED`.

## Layout (ADR 0004)

`repositories/order_repository.py` is the only file issuing ORM queries for
`Order`/`OrderItem`/`OrderStatusAudit`. `OrderOutboxEvent` rows are created directly from
`OrderService` (same convention as `apps.customers.services.registration_service` ->
`CustomerOutboxEvent`), not through the repository.

Calls, all through the other module's sanctioned `services/` entry point -- `orders` never
imports any of these modules' `models`/`repositories` directly:

- `apps.cart.services.cart_service.CartService` -- `get_active_cart()`/`price_cart()` to read
  and re-price the customer's cart, `clear()` to empty it after checkout.
- `apps.branches.services.branch_service.BranchService.get_by_id()` -- the branch's
  `delivery_fee`/`minimum_order_amount`.
- `apps.customers.services.address_service.AddressService.get_owned_by_customer_id()` --
  added by this Task: a non-raising, cross-module ownership lookup (`Address | None`) for a
  caller that already resolved `customer_id` itself, mirroring the existing non-raising
  convention `BranchService.get_by_id()`/`ProfileService.get_by_id()` already use.
- `apps.products.services.product_service.ProductService.get_by_id()` -- product name(s) for
  the `OrderItem` snapshot.

`Order.branch` is a real lazy string FK (`models.ForeignKey("branches.Branch", ...)`), same
pattern as `apps.cart.models.Cart.branch` -- an order genuinely belongs to exactly one real
branch row. `Order.customer_id` is a plain field, not a cross-app FK, same pattern as
`Cart.customer_id`. `OrderItem.product_id` is a plain, nullable field (not even a lazy string
FK) -- an `OrderItem` is an immutable historical snapshot that must survive its source
`Product` being edited or deleted entirely.

## Authorization

`IsAuthenticated` only -- every endpoint resolves the acting customer from `request.user` via
`ProfileService.get_profile()`, never from a client-supplied id (same pattern as
`apps.cart.api.views._customer_id_for`). An order id that exists but belongs to a different
customer returns `404`, never `403` (same pattern as `apps.cart.api.views.CartItemDetailView`).

## `api/` endpoints

- `POST /api/v1/orders/checkout/` -- `address_id` body, mandatory `Idempotency-Key` header.
  `201` with the created `Order` (or the first response, replayed, on a duplicate key).
  `400` for a missing header, an empty/mismatched cart, or a subtotal below the branch
  minimum; `404` for an address not owned by this customer.
- `GET /api/v1/orders/` -- the authenticated customer's own orders.
- `GET /api/v1/orders/<id>/` -- one of the authenticated customer's own orders.

Publishes: `OrderCreated` (`orders.events` / `order.created.v1`) on checkout;
`OrderConfirmed` (`orders.events` / `order.confirmed.v1`) on transition to `CONFIRMED`
(Issue #198's job to trigger -- not reachable from this Task's own endpoints).
