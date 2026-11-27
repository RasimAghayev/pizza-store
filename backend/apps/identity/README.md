# Identity

Owns authentication primitives: the custom `User` model (email as `USERNAME_FIELD`, no
separate username), the `Email` domain value object, credential verification
(`AuthenticationService.verify_credentials`), and the JWT/refresh-token session lifecycle
(`SessionService.login/refresh/logout`, `TokenService`, `RefreshToken` — ADR 0006, Issue #129).
Registration goes through `RegistrationService.register`, which validates the email, raises
`EmailAlreadyRegisteredError` if it's already taken, and otherwise delegates to
`UserRepository`. Called by `apps.customers.services.registration_service.RegistrationService`
(Issue #176) -- the sanctioned entry point for `customers` to create the `identity.User` row
behind a new customer account; `customers` never imports `identity.models`/`repositories`
directly, per ADR 0004.

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

`services/password_recovery_service.py::PasswordRecoveryService` (Issue #177) owns password
reset -- it stays in `identity`, not `customers`, since resetting a credential is identity's
own domain and needs no customer-profile concept. `request_reset(email)` is a silent no-op for
an unknown email (account-enumeration defense: the view returns the same generic `200`
response either way); on a known email it generates an opaque token, stores only its SHA-256
hash in the Redis cache keyed `pwreset:{token_hash}` with a 30-minute TTL
(`docs/database/redis-caching-and-ttl-policy.md`), and emails it via
`shared/notifications/console_gateway.py` directly -- never through
`apps.customers.services.notification_gateway.NotificationGateway`, which would be a backwards
`identity -> customers` call (ADR 0004: `customers` depends on `identity`, never the reverse).
`confirm_reset(token, new_password)` validates and deletes that cache entry (single-use even
within the TTL window), sets the new password via the new `UserRepository.set_password`, and
calls the new `TokenService.revoke_all_for_user`/`RefreshTokenRepository.revoke_all_for_user`
to kill every one of that user's existing refresh-token families -- the same
stolen-token-response machinery `TokenService.rotate_refresh_token` uses (ADR 0006), reused
here so a password reset invalidates every existing session, not just the one tied to whichever
refresh token happens to be presented next. `services/user_lookup_service.py::UserLookupService`
(`get_by_id`, raising `UserNotFoundError`) is the sanctioned read-only entry point
`apps.customers.services.verification_service.VerificationService` (Issue #177) uses instead of
importing `identity.models`/`repositories` directly, per ADR 0004.

`api/` exposes three endpoints — `POST /api/v1/auth/{login,refresh,logout}` — documented in
full in `docs/api/conventions.md` (client-type header, CSRF scoping, rate limits, the
`SameSite=Strict`/CORS caveat). `backend/apps/identity/tests/integration/test_auth.py`
covers: an issued access token verifies against the signing key and a hashed refresh token
is persisted; refresh rotates the token and the old one is rejected; reusing an
already-rotated token revokes the whole token family (stolen-token detection); and the
per-account login throttle rejects the request past its limit. `POST
/api/v1/auth/password-reset/{request,confirm}/` (Issue #177) are documented alongside the rate
limits above in `docs/api/conventions.md`.

Publishes: none.
