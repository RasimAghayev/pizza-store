# Products

Owns the pizza product catalog and its deterministic price-from-selected-options
calculation (Issue #181): `Product` (name, description, `base_price`, `is_active`),
`OptionGroup`/`OptionChoice` (one generic size/dough/crust/cheese/sauce pair, not five
bespoke models), `Topping`/`ProductTopping` (default-included vs. add-on), and `Allergen`
(M2M to both `Product` and `Topping`).

## Scope boundaries (deliberately out of this Task)

- **Per-branch menu availability** (which branches sell which products) is Issue #182's
  concern. `Product` is org-scoped only — it carries a plain `organization_id` field (same
  no-cross-app-FK pattern as `apps.identity.RoleAssignment`, see `models/product.py`), never
  a `branch_id`.
- **Inventory** is Phase 12. `Topping.sku_reference` is the named, not-yet-built integration
  point — nothing in this module reads or writes it beyond storing the string.
- **Promotions/discounts** are a separate future module (ADR 0001). `domain/pricing.py`
  computes only the deterministic base price from selected options; there is no discount
  hook anywhere in this calculation.

## Pricing rules (`domain/pricing.py`)

Pure functions, no Django import (ADR 0004) — `ProductSelection` is a plain dataclass holding
a build's `base_price`, `option_choice_deltas`, and `non_default_topping_deltas`;
`calculate_price()` sums them into a unit price, then multiplies by quantity **last**, after
per-unit summation is complete (quantity never distributes across individual deltas).

**Half-and-half** — the master prompt names half-and-half pizzas without specifying a
pricing formula, so this Task's own choice, stated explicitly per the Issue's own
requirement rather than left implicit: each half is an independent, fully-specified
`ProductSelection` (its own product's base price + its own option deltas + its own
non-default topping deltas); the two halves' **unit prices are averaged, not summed** — a
half-and-half pizza costs the same on average as picking either half outright, not double.
Quantity is applied to that averaged unit price, same "last" rule as a regular build. The
final result is explicitly rounded to 2 decimal places (`ROUND_HALF_UP`) rather than relying
on implicit serializer-level rounding, since averaging two prices can produce a third decimal
place (e.g. `(10.00 + 10.01) / 2 = 10.005`).

**Allergens** — a product's allergen list unions its own `allergens` and its
**default-included toppings'** allergens only (`AllergenRepository
.for_product_union_default_toppings`) — an optional add-on topping's allergen is the
customer's own choice to add, so it is deliberately excluded from the product's base
allergen profile.

## Layout (ADR 0004)

`repositories/` are the only files issuing ORM queries. `ProductService` is the sanctioned
cross-module entry point for Product/OptionGroup/OptionChoice/Topping-attachment/allergen
reads; `CatalogService` owns the shared Topping/Allergen catalog CRUD; `PricingService`
translates ORM rows into `domain.pricing.ProductSelection`s and calls `calculate_price()` —
this is what `POST /api/v1/products/<id>/price-quote/` calls today, and what Phase 11's
cart/checkout will call for the same calculation (named explicitly in Issue #181).

Calls `apps.restaurants.services.organization_service.OrganizationService.get_by_id()` — see
`backend/apps/restaurants/README.md` — to validate a new Product's `organization_id` exists
at create time; `products` never imports `apps.restaurants.models`/`repositories` directly.

## Authorization

Uses `shared/permissions/base.py::TwoStepPermission`, scoped by the `products.view`/
`products.edit` permission strings (`apps/identity/domain/rbac.py`). `products.edit` is
granted only to the two org-scoped roles (`SUPER_ADMIN`, `ORGANIZATION_OWNER`) that can ever
satisfy the object-level check against a Product's `organization_id` — a purely
branch-scoped assignment's `branch_id` can never match (Product's `scope_branch_id()` always
returns `None`), so granting a branch-scoped role `products.edit` would be a permission that
structurally can never pass step 2. Every staff role instead holds `products.view`.

Topping/Allergen are a **platform-wide catalog** with no organization/branch scope of their
own. `_PlatformCatalogScoped`'s `scope_organization_id`/`scope_branch_id` hooks always return
`None` regardless of the object passed in, so per `TwoStepPermission`'s matching rules, only
an *unscoped* `products.edit` grant (e.g. Super Admin) can create/edit/delete a catalog row.
An org-scoped Organization Owner can still attach an *existing* catalog topping to their own
product via `ProductService.attach_topping` — a separate, Product-scoped check — but cannot
create a brand-new platform-wide topping.

`Product`/`OptionGroup`/`OptionChoice`/`Topping`/`Allergen` read, and `price-quote`, are
public (`AllowAny`) — menu-browsing and price-checking need this before login exists, same
pattern as Restaurant/Branch (Issue #180). Listing products requires an explicit
`organization_id` query filter — unlike Restaurant/Branch, Product is per-tenant menu data,
so there is no sensible "every product across every organization" public listing.

## `api/` endpoints

- `GET /api/v1/products/?organization_id=<id>` / `POST /api/v1/products/`
- `GET/PATCH/DELETE /api/v1/products/<id>/`
- `GET/POST /api/v1/products/<id>/option-groups/`
- `GET/POST /api/v1/products/<id>/option-groups/<group_id>/choices/`
- `GET/POST /api/v1/products/<id>/toppings/` (attach an existing catalog topping)
- `DELETE /api/v1/products/<id>/toppings/<topping_id>/` (detach)
- `GET /api/v1/products/<id>/allergens/` (own + default-topping union, read-only)
- `POST /api/v1/products/<id>/price-quote/` — `<id>` is the first/primary product; an
  optional `other_half` body field (with its own `product_id` and selection) requests a
  half-and-half quote instead of a single-product one.
- `GET/POST /api/v1/products/toppings/` and `GET/PATCH/DELETE
  /api/v1/products/toppings/<id>/` — the shared catalog, unscoped-write-only.
- `GET/POST /api/v1/products/allergens/` and `GET/DELETE
  /api/v1/products/allergens/<id>/` — the shared catalog, unscoped-write-only.

Publishes: none.
