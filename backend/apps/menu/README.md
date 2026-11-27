# Menu

Owns the per-branch menu (Issue #182): `MenuCategory` (`organization_id, name,
display_order` — an org-wide catalog of categories, e.g. "Pizzas"/"Sides", not a per-branch
concept) and `MenuItem` (`branch, product, category, is_available, available_from,
available_until, display_order` — the row that links one `Branch` to one `Product`, unique
per branch+product). `MenuItem.branch`/`MenuItem.product` are lazy string-reference FKs
(`models.ForeignKey("branches.Branch", ...)` / `models.ForeignKey("products.Product", ...)`)
— this module never imports `apps.branches.models`/`apps.products.models` directly (ADR
0004); every repository method takes `branch_id: int`/`product_id: int`, never a model
instance.

Master prompt §11: "one branch's menu and inventory are not automatically dependent on
another's" — the same `Product` catalog (Issue #181, org-scoped) can be offered at some
branches and not others, and independently marked unavailable per branch. `menu_for_branch`
only ever reads rows scoped to the one `branch_id` it's given; a product on one branch's
menu has no effect on any other branch, whether or not it shares the same underlying
`Product` row.

## Availability (`domain/availability.py`)

Pure, Django-import-free (ADR 0004) — `is_available_at` takes the item's own
`is_available`/`available_from`/`available_until` plus a moment to check against.
`available_from`/`available_until` are both nullable: left null, the item has no window
restriction and is available whenever `is_available=True`; set, the window is half-open
(`available_from` inclusive, `available_until` exclusive), time-of-day only. **A window that
crosses midnight (`available_from > available_until`) is not supported** — stated explicitly
rather than left to be assumed, same spirit as Issue #181's half-and-half pricing rule: an
overnight item is out of this Task's scope.

## Cross-organization integrity

`MenuService.create_item`/`update_item` validate that a `MenuItem`'s `product`/`category`
belong to the *same* organization as its `branch` (resolved through
`BranchService.organization_id_for_restaurant`, see "Authorization" below) — this is a data
integrity check, not merely an authorization one: `TwoStepPermission`'s object-level check on
create only verifies the target *branch* is in the requester's own scope, so without this a
user could still link their own branch to another organization's product or category (not a
privilege escalation, but a nonsensical cross-tenant row). A duplicate `(branch, product)`
pair is rejected at both the DB level (`UniqueConstraint`) and the service layer (a clean
`DuplicateMenuItemError` instead of surfacing a raw `IntegrityError`).

## Layout (ADR 0004)

`repositories/` are the only files issuing ORM queries. `MenuService` is the sanctioned
cross-module entry point. Calls `apps.branches.services.branch_service.BranchService.
{get_by_id,organization_id_for_restaurant}()` (see `backend/apps/branches/README.md`) to
validate a new `MenuItem`'s `branch_id` and to resolve the `TwoStepPermission` scope hook,
since neither `MenuItem` nor `Branch` stores an `organization_id` column directly. Calls
`apps.products.services.product_service.ProductService.get_by_id()` (see
`backend/apps/products/README.md`) to validate a new `MenuItem`'s `product_id`. `menu` never
imports either module's `models`/`repositories` directly.

## Authorization

Uses `shared/permissions/base.py::TwoStepPermission`, scoped by the `menu.view`/`menu.edit`
permission strings (`apps/identity/domain/rbac.py`). Unlike `products.edit` (always denied to
branch-scoped roles, since `Product.scope_branch_id()` is always `None`), `menu.edit` **is**
granted to branch-scoped roles (`RESTAURANT_MANAGER`, `BRANCH_MANAGER`, the same set already
holding `branches.edit`) because `MenuItem.scope_branch_id()` returns its own real branch id
— a branch-scoped holder can manage only their own branch's items. `MenuCategory` is
org-wide like `Product` (`scope_branch_id()` always `None`), so a branch-scoped role's
`menu.edit` grant is correctly denied at step 2 when attempting to create a new category —
no separate rule is needed, the same self-enforcing mechanism already relied on for
Branch/Organization creation (Issue #180). Every other staff role holds `menu.view`.

`GET /api/v1/branches/<branch_id>/menu/` (the public, customer-facing listing — only
currently-available items) is `AllowAny`, same visibility as Branch/Product's own public read
paths. Every `/api/v1/menu/...` endpoint (categories and the staff item list/detail) is
staff-only, authenticated via `TwoStepPermission` for both reads and writes — unlike
Branch/Product, neither the category catalog nor the full (unfiltered) per-branch item list
has a public read path of its own, the same staff-only precedent as `Organization` (Issue
#180).

## `api/` endpoints

- `GET /api/v1/branches/<branch_id>/menu/` — public, availability-filtered; mounted directly
  in `config/urls.py` under the `branches/` prefix rather than through
  `apps.branches.api.urls`, so `apps.menu` stays the sole owner of this view and
  `apps.branches` never imports `apps.menu` (ADR 0004's dependency direction: `menu` depends
  on `branches`/`products`, never the reverse).
- `GET/POST /api/v1/menu/categories/?organization_id=<id>` and `GET/PATCH/DELETE
  /api/v1/menu/categories/<id>/`
- `GET /api/v1/menu/items/?branch_id=<id>` and `POST /api/v1/menu/items/` (staff's own,
  unfiltered item list — includes unavailable items and items outside their window) and
  `GET/PATCH/DELETE /api/v1/menu/items/<id>/`

Publishes: none.
