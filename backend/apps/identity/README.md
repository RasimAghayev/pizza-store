# Identity

Owns authentication primitives: the custom `User` model (email as `USERNAME_FIELD`, no
separate username), the `Email` domain value object, credential verification
(`AuthenticationService.verify_credentials`), and the JWT/refresh-token session lifecycle
(`SessionService.login/refresh/logout`, `TokenService`, `RefreshToken` — ADR 0006, Issue #129).
Registration goes through `RegistrationService.register`, which validates the email and
delegates to `UserRepository`.

`UserRepository` and `RefreshTokenRepository` are the only files in this module allowed to
issue an ORM query, per ADR 0004.

`api/` exposes three endpoints — `POST /api/v1/auth/{login,refresh,logout}` — documented in
full in `docs/api/conventions.md` (client-type header, CSRF scoping, rate limits, the
`SameSite=Strict`/CORS caveat). `backend/apps/identity/tests/integration/test_auth.py`
covers: an issued access token verifies against the signing key and a hashed refresh token
is persisted; refresh rotates the token and the old one is rejected; reusing an
already-rotated token revokes the whole token family (stolen-token detection); and the
per-account login throttle rejects the request past its limit.

Out of scope for this module today, by design:

- RBAC (`role_assignments`, permission+scope checks; `permissions/` is present but empty) —
  deferred to Phase 10 per ADR 0006's "Consequences" section.

Publishes: none.
