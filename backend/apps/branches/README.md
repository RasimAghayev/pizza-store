# Branches

Owns the `Branch` bounded context (Issue #180): a physical location (`restaurant, name,
address, latitude, longitude, phone, delivery_radius_km, delivery_fee,
minimum_order_amount, average_prep_time_minutes, capacity, is_active, created_at`), its
weekly `BusinessHours` (`branch, weekday, opens_at, closes_at`, unique per
branch+weekday), and its ad-hoc `BranchClosure` windows (`branch, starts_at, ends_at,
reason`). `Branch.restaurant` is a lazy string-reference FK
(`models.ForeignKey("restaurants.Restaurant", ...)`) — this module never imports
`apps.restaurants.models`/`repositories` (ADR 0004); every repository method takes
`restaurant_id: int`, never a `Restaurant` instance.

`domain/opening_hours.py` is a pure domain layer with zero Django imports — `is_open_at`
takes plain `HoursWindow`/`ClosureWindow` dataclasses (translated from ORM rows by
`BranchService`) and decides whether a branch is open at a given moment, applying closures
as an override on top of the weekly schedule. A weekday with no `BusinessHours` row is
treated as closed — "closed day = absence of row" is a deliberate, documented convention
rather than a nullable/boolean column, per Issue #180's instruction to pick one approach and
apply it consistently.

`BranchRepository`/`BusinessHoursRepository`/`BranchClosureRepository` are the only files in
this module allowed to issue an ORM query, per ADR 0004. `BranchRepository.within_delivery_
radius_of` computes the Haversine distance entirely in SQL via `django.db.models.functions`
(`ACos`, `Cos`, `Sin`, `Radians`) — no PostGIS is installed — clamping the cosine argument to
`[-1, 1]` to avoid floating-point rounding pushing `ACos` outside its domain.

`BranchService` calls `apps.restaurants.services.restaurant_service.RestaurantService.
get_by_id()` (see `backend/apps/restaurants/README.md`) to validate a new Branch's
`restaurant_id` on create and to resolve `organization_id_for_restaurant()` — the
`TwoStepPermission` scope hook Branch needs for RBAC, since Branch itself stores no
`organization_id` column.

Authorization uses `shared/permissions/base.py::TwoStepPermission`, scoped by the
`branches.view`/`branches.edit` permission strings (`apps/identity/domain/rbac.py`). Reading
a branch, its hours, its closures, `is-open`, and `nearby` are all public (`AllowAny`) —
customers need these before login exists. Create/update/delete and setting
hours/closures require `branches.edit`, re-scoped by step 2 against the branch's owning
organization (create) or the branch itself (update/delete/hours/closures). A branch-scoped
assignment can never create a new Branch — the provisional, unsaved instance built from the
request payload has `pk=None`, which only an org-scoped or unscoped holder can match.

`api/` exposes:

- `GET/POST /api/v1/branches/` and `GET/PATCH/DELETE /api/v1/branches/<id>/`
- `GET /api/v1/branches/nearby/?lat=&lon=` — branches whose own `delivery_radius_km` covers
  the given point.
- `GET /api/v1/branches/<id>/is-open/`
- `GET/POST /api/v1/branches/<id>/hours/`
- `GET/POST /api/v1/branches/<id>/closures/` and `DELETE
  /api/v1/branches/<id>/closures/<closure_id>/`

Publishes: none.
