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

`services/social_login_service.py::SocialLoginService.complete_login(provider_id, token)`
(Issue #178) backs `POST /api/v1/auth/social/{google,apple,facebook}/`. `django-allauth` is
used **only** for the provider token handshake and `SocialAccount`-to-`identity.User`
linking (`django.contrib.sites`/`sessions`, `allauth`, `allauth.account`,
`allauth.socialaccount` in `INSTALLED_APPS`) -- its own `allauth.urls`/`allauth.headless` URL
surface is never mounted, and no allauth session cookie is ever exposed to the API client
(verified by a dedicated test asserting no `sessionid` cookie in the response). Each call
builds a disposable `HttpRequest` + `signed_cookies`-backed session
(`_build_isolated_request`), re-entered via `allauth.core.context.request_context` so
allauth-internal code reading the context-local request also sees it, and discards it once
`allauth.socialaccount.helpers.complete_social_login` returns -- the real client
request/response never receives anything allauth attached to that disposable request/session.
`PizzaStoreSocialAccountAdapter` (the project's `SOCIALACCOUNT_ADAPTER`) overrides only
`pre_social_login`: when the provider's **verified** email matches an existing, unlinked
`identity.User`, it raises `AccountExistsUnlinkedError` (surfaced as `400 validation_error`
with an `account_exists_unlinked` detail key) rather than silently merging into that account --
a provider-claimed email that isn't verified is deliberately never matched at all (not even to
reject), since doing so would let an always-unverified provider (Facebook's classic Graph API
response never reports `verified`, by allauth's own design) be used as an email-existence
oracle. On success, `complete_login` calls
`apps.customers.services.registration_service.RegistrationService.provision_customer(user)` --
the same create-`Customer`/assign-`customer`-role/publish-`CustomerRegistered` step
`RegistrationService.register()` already uses for email/password sign-up (Issue #176), now
factored out so a social-login-created `User` gets an identical `Customer` profile on its
first-ever login, idempotent on every later login -- then
`SessionService.issue_tokens_for(user)` (also factored out of `SessionService.login()`) to
mint the platform's real RS256/refresh pair exactly as `LoginView` does. Provider token shapes
are not symmetric: Google/Apple only ever send `id_token`; Facebook sends either `id_token`
(Limited Login) or `access_token` (classic OAuth2) -- see
`api/serializers.py::SocialLoginSerializer` and each provider's own `verify_token()` in
django-allauth. `backend/apps/identity/tests/integration/test_social_login.py` and
`tests/unit/test_social_login_service.py` cover: a new social identity creates a
`User`+`Customer`+role assignment and a usable token pair for each of the three providers; a
second login with the same identity reuses the existing `User`/`Customer`; a verified-email
collision with an existing unlinked account is rejected and creates nothing; an
always-unverified collision (Facebook) still fails closed without merging; and no `sessionid`
cookie ever appears in the response.

Publishes: none.
