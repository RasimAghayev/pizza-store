# Security

Security Architecture, OWASP ASVS/Top 10 application, PCI DSS principles, privacy/retention policy.

See [ADR 0006](../adr/0006-security-architecture-baseline.md) for the JWT/refresh token
lifecycle, RBAC-to-roles mapping and multi-tenant isolation boundary, secret management
strategy, data-encryption-at-rest field list, and password hashing decision.

[role-permission-matrix.md](role-permission-matrix.md) — every master prompt §11 role against
the permissions it actually holds, kept in sync with
`backend/apps/identity/domain/rbac.py::ROLE_PERMISSIONS` (Issue #183).

> Status: Phase 1 — security architecture baseline decided (ADR 0006); implementation is
> Phase 6 (auth baseline) and Phase 10 (RBAC).
