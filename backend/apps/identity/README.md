# Identity

Owns authentication primitives: the custom `User` model (email as `USERNAME_FIELD`, no
separate username), the `Email` domain value object, and credential verification
(`AuthenticationService.verify_credentials`). Registration goes through
`RegistrationService.register`, which validates the email and delegates to `UserRepository` —
the only file in this module allowed to issue an ORM query, per ADR 0004.

Out of scope for this module today, by design:

- RBAC (`role_assignments`, permission+scope checks) — deferred to Phase 10 per ADR 0006's
  "Consequences" section.
- The JWT login/refresh API (`api/`, `permissions/` are present but empty) — Issue #129.
- `PASSWORD_HASHERS` wiring to Argon2id — also Issue #129; this module only requires
  `check_password()`/`set_password()` to work against whichever hasher is configured.

Publishes: none.
