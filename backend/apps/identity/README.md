# Identity

Owns authentication primitives: the custom `User` model (email as `USERNAME_FIELD`, no
separate username), the `Email` domain value object, credential verification
(`AuthenticationService.verify_credentials`), and the JWT/refresh-token session lifecycle
(`SessionService.login/refresh/logout`, `TokenService`, `RefreshToken` — ADR 0006, Issue #129).
Registration goes through `RegistrationService.register`, which validates the email and
delegates to `UserRepository`.

Also owns RBAC (Issue #175, ADR 0006): `RoleAssignment` (`user, role_code, organization_id,
branch_id`), the static `RoleCode`/`ROLE_PERMISSIONS` mapping
(`domain/rbac.py` — seeded in code, not a database-editable table, per the ADR), and
`RoleAssignmentService.assign/roles_for`, the explicit cross-module entry point other modules
call to grant a role — e.g. `apps.customers.services.registration_service.RegistrationService`
(Issue #176) assigning `customer` on sign-up. `SessionService.login` loads the user's role
assignments and populates the JWT's `roles`/`org_id`/`branch_id` claims; on `refresh`, those
claims are carried forward unchanged from the `RefreshToken.roles_snapshot` captured at login
rather than re-queried — **a role change only takes effect on that account's next full
login**, a deliberate limitation (`TokenService.rotate_refresh_token`).

`JWTCookieOrHeaderAuthentication` (`api/authentication.py`, the new
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` default, Issue #175) resolves `request.user`
from the access token for every protected endpoint from here onward; `login`/`refresh`/
`logout`/`ping` stay public by explicitly setting `authentication_classes = []`.
`shared/permissions/base.py::TwoStepPermission` is the reusable authorization check later
modules (restaurants/branches/products/menu, Phase 10) use against it — it calls
`request.user.has_rbac_permission()`/`.role_assignments_granting()` (duck-typed methods on
`User`, see below) rather than importing this app, per ADR 0004.

`UserRepository`, `RefreshTokenRepository`, and `RoleAssignmentRepository` are the only files
in this module allowed to issue an ORM query, per ADR 0004.

`api/` exposes three endpoints — `POST /api/v1/auth/{login,refresh,logout}` — documented in
full in `docs/api/conventions.md` (client-type header, CSRF scoping, rate limits, the
`SameSite=Strict`/CORS caveat). `backend/apps/identity/tests/integration/test_auth.py`
covers: an issued access token verifies against the signing key and a hashed refresh token
is persisted; refresh rotates the token and the old one is rejected; reusing an
already-rotated token revokes the whole token family (stolen-token detection); and the
per-account login throttle rejects the request past its limit.

Publishes: none.
