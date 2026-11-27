# Cart

Owns the branch-scoped shopping cart a customer builds before checkout (Issue #196):
`Cart` (one row per `(customer_id, branch_id)` a customer has ever added an item to) and
`CartItem` (one customer-built pizza selection -- a single product build, or a
half-and-half build, plus quantity and a free-text note).

## Scope boundaries (deliberately out of this Task)

- **Checkout / converting a cart into an `Order`** is Issue #197's job, not this one's.
- **Promotions/discounts** are a separate future module (ADR 0001) -- nothing in this
  module's pricing path has a discount hook.
- **Payment** is Issue #198's job.

## Branch-switch decision

Issue #196 leaves "what happens when a customer tries to add an item from a different
branch than their currently-open cart" unspecified by design, requiring this Task's own
single, consistently-applied choice (same pattern as Issue #181's half-and-half pricing
decision). **This Task rejects the switch**, not silently clear-and-switch: `POST
/api/v1/cart/` returns `409 conflict` when the customer already has a non-empty cart for a
different branch, naming the existing branch so the client can show its own "switching
branches clears your cart -- continue?" confirmation and then explicitly call `DELETE
/api/v1/cart/` before retrying. Rejecting keeps the mutation explicit and side-effect-free
from the server's point of view, rather than this module silently discarding a customer's
existing selection on their behalf. See `domain/branch_policy.py::can_add_to_branch` for the
pure rule and its own rationale, and `services/cart_service.py::CartService.get_or_create_cart`
for where it is enforced.

A customer may accumulate multiple empty `Cart` rows across branches over time (left over
from past switches); these are harmless and never surfaced by the API -- `GET /api/v1/cart/`
only ever shows the one cart, if any, that currently has items
(`CartRepository.active_cart_for_customer`).

## Live re-pricing

`CartItem.unit_price_snapshot` is captured once, at add-time, for audit/history purposes
only -- it is **never** the authoritative price shown to the customer. Every read
(`GET /api/v1/cart/`, and the response to every mutation) re-quotes each item live through
`PricingService.quote()` so a later `base_price`/option-price change can never leave a stale
price on screen.

A line's `unit_price` and `line_total` are each computed by an **independent, direct**
`PricingService.quote()` call (`quantity=1` and `quantity=item.quantity` respectively) --
never `unit_price * item.quantity` computed by hand. `calculate_price()` rounds the real
quantity-multiplied total in one step (`apps/products/domain/pricing.py`), which is not
always identical to rounding a `quantity=1` unit price first and then multiplying that
*already-rounded* value by quantity -- re-deriving `line_total` from `unit_price` would
silently drift from what a fresh quote call returns on a half-and-half build whenever the
unrounded per-unit average lands on a third decimal place (e.g. `(10.00 + 10.01) / 2 =
10.005`). The cart `total` is the `Decimal` sum of every line's independently-quoted
`line_total` -- never `float`.

## Layout (ADR 0004)

`repositories/` is the only file issuing ORM queries for `Cart`/`CartItem`. `CartService` is
the sanctioned entry point: `get_or_create_cart`, `add_item`, `update_item_quantity`,
`remove_item`, `clear`, `current_total`, plus `get_priced_active_cart` (the one call
`GET /api/v1/cart/` and every mutation's response use to return the live-priced cart).

Calls, all through the other module's sanctioned `services/` entry point -- `cart` never
imports any of these modules' `models`/`repositories` directly:

- `apps.products.services.pricing_service.PricingService.quote()` -- live pricing for a
  single-build or half-and-half line (named explicitly in Issue #181 as Phase 11's job).
- `apps.menu.services.menu_service.MenuService.is_orderable_now()` -- added by this Task;
  rejects an item for a product with no `MenuItem` row on the requested branch at all, or
  one that exists but is outside its availability window right now.
- `apps.branches.services.branch_service.BranchService.get_by_id()` -- validates
  `branch_id` exists before creating a `Cart` row.
- `apps.customers.services.profile_service.ProfileService.get_by_id()` -- added by this
  Task; validates a `customer_id` exists, called only when `get_or_create_cart` is about to
  insert a brand-new `Cart` row, never on a read of an already-existing one (`Cart.customer_id`
  is a plain field, not a cross-app FK, same pattern as `apps.products.models.Product
  .organization_id` -- see `models/cart.py`). The same module's `ProfileService.get_profile()`
  (keyed by `identity.User.pk`, not `Customer.pk`) is what `api/views.py` calls on every
  request to resolve the authenticated user to their own `customer_id` in the first place --
  a client can never supply its own `customer_id` (Security Requirements below).

`Cart.branch` is a lazy string FK (`models.ForeignKey("branches.Branch", ...)`), same
pattern as `apps.menu.MenuItem.branch` -- a cart is genuinely owned/composed by its branch
(cascade-delete makes sense), unlike the looser, no-FK `customer_id` relationship above.
`CartItem.product` is likewise a lazy string FK to `products.Product` (nullable -- a
half-and-half item has no single product; `CartItem.half_and_half` stores both halves'
plain product/option/topping ids as JSON instead, the same shape `PricingService.quote
(half_and_half=...)` expects).

## Authorization

`IsAuthenticated` only, no RBAC (`TwoStepPermission` is for staff-facing resources) -- every
endpoint resolves the acting customer from `request.user` via `ProfileService.get_profile()`,
never from a client-supplied id in the request body or URL (Security Requirements). A cart
item id that exists but belongs to a different customer's cart returns `404`, never `403`
(same pattern as `apps.customers.api.views.AddressDetailView`) -- a request can't distinguish
"not yours" from "doesn't exist".

## `api/` endpoints

- `GET /api/v1/cart/` -- the customer's current cart, live-repriced. A customer with no
  cart (or only empty ones) gets `{"id": null, "branch_id": null, "items": [], "total":
  "0.00"}`, not a 404 -- the cart is a singleton resource from the client's point of view.
- `POST /api/v1/cart/` -- add an item (`branch_id` + either `product_id` or `half_and_half`
  + `option_choice_ids`/`topping_ids`/`quantity`/`note`). `409 conflict` if the customer's
  existing non-empty cart is for a different branch; `400` if the product is not orderable
  at this branch right now or the body doesn't supply exactly one of `product_id`/
  `half_and_half`.
- `DELETE /api/v1/cart/` -- clear the active cart (`204`). Also how a client complies with
  the `409` above before switching branches.
- `PATCH /api/v1/cart/items/<id>/` -- update an item's quantity.
- `DELETE /api/v1/cart/items/<id>/` -- remove an item.

Publishes: none (checkout, Issue #197, is where a cart's contents become a real domain
event).
