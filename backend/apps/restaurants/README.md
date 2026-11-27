# Restaurants

Owns the `Organization`/`Restaurant` bounded context (Issue #180). An `Organization` (`name,
owner_user_id, created_at`) is the top-level tenant; a `Restaurant` (`organization, name,
description, created_at`) belongs to exactly one `Organization` via a lazy string-reference
FK (`models.ForeignKey("restaurants.Organization", ...)`). `Organization` is modeled inside
this module rather than a separate app, per Issue #180's own resolution of that ambiguity —
it has no independent lifecycle or API surface beyond being the thing a Restaurant belongs
to and the unit RBAC scopes against.

`OrganizationRepository`/`RestaurantRepository` are the only files in this module allowed to
issue an ORM query, per ADR 0004. `OrganizationService.create/get_by_id/update/delete/
list_visible_to` and `RestaurantService.create/get_by_id/list_all/update/delete` are the
sanctioned cross-module entry points; `RestaurantService.create` raises
`OrganizationNotFoundError` when the given `organization_id` doesn't exist, which the API
layer translates into the standard `validation_error` envelope rather than a 500.

Called by `apps.branches.services.branch_service.BranchService` (Issue #180) to validate a
new Branch's `restaurant_id` and to resolve a Branch's owning `organization_id` for RBAC
scope checks — the sanctioned entry point for that read, per ADR 0004; `branches` never
imports `restaurants.models`/`repositories` directly.

Authorization uses `shared/permissions/base.py::TwoStepPermission`, scoped by the
`restaurants.view`/`restaurants.edit` permission strings (`apps/identity/domain/rbac.py`).
`Organization` has no public read path — every `OrganizationListCreateView`/
`OrganizationDetailView` request requires an authenticated holder of `restaurants.view` (GET)
or `restaurants.edit` (write), re-scoped by step 2 against the Organization's own `pk`.
`Restaurant` read is public (`AllowAny`) for menu-browsing; only create/update/delete require
`restaurants.edit`, scoped by `organization_id`. Creating a brand-new `Organization`/
`Restaurant` re-derives scope against a provisional, unsaved model instance built from the
request payload — its `pk` is always `None`, so only an unscoped (e.g. Super Admin) or, for
Restaurant, a matching-`organization_id`-scoped holder can open one; a Restaurant-scoped
assignment never exists since Restaurant itself carries no RBAC scope.

`api/` exposes:

- `GET/POST /api/v1/restaurants/organizations/` and `GET/PATCH/DELETE
  /api/v1/restaurants/organizations/<id>/` — staff-only.
- `GET/POST /api/v1/restaurants/` and `GET/PATCH/DELETE /api/v1/restaurants/<id>/` — read is
  public, writes require `restaurants.edit` scoped to the restaurant's organization.

Publishes: none.
