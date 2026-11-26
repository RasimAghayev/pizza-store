# ADR 0006: Security Architecture Baseline

## Status

Accepted

## Context

Master prompt §12 requires OWASP ASVS/Top 10 compliance, RBAC with room for ABAC, JWT
lifecycle with refresh token rotation, secure cookies, CSRF/XSS/SQL-injection protection,
secret management, and data encryption at rest. §11 fixes the role list (Guest, Customer,
Verified Customer, Loyalty Member; Super Admin, Organization Owner, Restaurant Manager, Branch
Manager, Cashier, Kitchen Manager/Staff, Delivery Manager, Courier, Inventory Manager,
Marketing Manager, Accountant, Customer Support) and requires backend-enforced multi-tenant
data isolation — a manager must only reach their own restaurant/branch's data — plus audit
logging of critical operations.

None of this has a concrete design yet. Without fixing it before Phase 6 (which builds the
auth baseline) and Phase 10 (which implements RBAC against it), authentication and
authorization would each get designed ad hoc mid-implementation, and the multi-tenant
isolation boundary — which touches every module, not just identity — would be inconsistent
across modules.

§11 implies, but does not name, a tenancy hierarchy: an **Organization** (the account that
owns one or more restaurant brands) contains **Restaurants** (brands), which contain
**Branches** (physical locations, already a separate entity from Restaurant per §11). This ADR
treats `organization_id` as the top-level multi-tenant boundary and `branch_id` as a
finer-grained scope within it, since the role list's hierarchy (Organization Owner →
Restaurant Manager → Branch Manager) only makes sense with Organization as the outermost
isolation unit.

No backend code exists yet; this ADR is written purely from §11/§12 and ADR 0001 (modular
monolith — authorization must be enforced inside each module's service layer, not centrally
bypassable).

## Decision

### JWT lifecycle and refresh token rotation

An access/refresh token pair, both issued by the `identity` module:

- **Access token**: JWT, `RS256`-signed (asymmetric — only the identity module holds the
  private signing key; any other module/future microservice verifies with the public key
  only, which keeps ADR 0001's eventual-extraction option open). Lifetime: 15 minutes. Claims:
  `sub` (user id), `roles` (role codes held), `org_id`/`branch_id` (tenant scope, null for
  customer-facing roles), `jti` (token id, for logging/correlation — not a revocation
  mechanism, see below), standard `iat`/`exp`.
- **Refresh token**: opaque random value (not a JWT — nothing to decode, so it is useless to
  an attacker without the DB lookup), persisted server-side in a `refresh_tokens` table
  (`id`, `user_id`, `token_hash` (hashed, never stored plaintext, same principle as a
  password), `issued_at`, `expires_at`, `revoked_at`, `replaced_by_id`, `device_label`,
  `ip_address`). Lifetime: 14 days.
- **Rotation**: rotate-on-use, single-use refresh tokens. Every `/auth/refresh` call revokes
  the presented refresh token and issues a brand-new access/refresh pair, linking the new row's
  `replaced_by_id` back to the old one (a "family" chain). If a refresh token that has already
  been rotated (its `revoked_at` is set) is presented again, this is treated as a stolen-token
  signal: the entire family is revoked immediately, forcing re-authentication on every device
  that held a token from that family.
- **Storage**: both tokens are delivered to browser clients as `httpOnly`, `Secure`,
  `SameSite=Strict` cookies — never `localStorage`/`sessionStorage`, so an XSS payload cannot
  read either token via JavaScript. The refresh cookie is scoped to the `/auth/refresh` path
  only, so it is never sent on ordinary API calls. Non-browser clients (the future courier
  mobile app) instead receive both tokens in the response body and are responsible for
  OS-level secure storage (e.g. Android Keystore/iOS Keychain); they send the access token via
  the `Authorization` header instead of a cookie.
- Because cookie-based auth is used for browser clients, every state-changing request also
  requires Django's CSRF token (`X-CSRFToken` header, double-submit cookie pattern) in
  addition to `SameSite=Strict` — `SameSite` alone does not cover every CSRF vector (e.g.
  subdomain-hosted attacker content), so both defenses stay layered.
- Key rotation: the signing key pair carries a `kid`; rotating to a new key pair keeps the old
  public key accepted for verification until the longest-lived access token issued under it
  (15 minutes) has expired, then retires it.

### RBAC and multi-tenant isolation

A permission is `<module>.<action>` (e.g. `orders.view`, `orders.refund`, `menu.edit`,
`inventory.adjust`). Each role from §11 maps to a fixed set of permissions, seeded at migration
time rather than editable at runtime — a runtime role/permission editor is out of scope until a
real need for custom roles is demonstrated (see Alternatives).

Two groups of roles, handled differently:

- **Staff roles** (Super Admin, Organization Owner, Restaurant Manager, Branch Manager,
  Cashier, Kitchen Manager/Staff, Delivery Manager, Courier, Inventory Manager, Marketing
  Manager, Accountant, Customer Support): a user holds a role via a `role_assignments` row
  carrying `(user_id, role_code, organization_id, branch_id)`. `branch_id` is null for
  roles scoped at the organization level (Organization Owner, Accountant, Marketing Manager)
  and set for branch-scoped roles (Branch Manager, Cashier, Kitchen Manager/Staff, Delivery
  Manager, Inventory Manager); Super Admin carries no scope at all (platform-wide, used only
  for platform operators, never a restaurant-chain employee). A user can hold multiple
  assignments (e.g. a Branch Manager at two branches), so scope lives on the assignment, not
  the user record.
- **Customer-facing roles** (Guest, Customer, Verified Customer, Loyalty Member): modeled as
  the same role mechanism but representing a progressive account state rather than an
  assignable staff role — Guest (browse/cart, no checkout) → Customer (checkout allowed, email
  unverified) → Verified Customer (email/phone verified, saved payment methods, full feature
  set) → Loyalty Member (Verified Customer plus loyalty-program permissions). These carry no
  `organization_id`/`branch_id` scope — a customer orders from any branch, they are not tenant
  bound.

Every authorization check is two-step and runs **only in the backend service layer** (§11's
explicit requirement — a frontend-hidden button is never the enforcement mechanism): (1) RBAC —
does any of this user's role assignments grant the requested permission; (2) scope filter — for
staff roles, does the requested resource's `organization_id`/`branch_id` match that assignment's
scope. Step 2 never trusts a client-supplied `branch_id` alone; it is always re-derived from the
resource being acted on (e.g. the order's own branch) and compared against the user's
assignment. ABAC is reserved for cases RBAC-plus-scope cannot express (e.g. "a Courier may only
update the location of an order currently assigned to them") — handled as an explicit ownership
check in that module's service layer, not a general-purpose policy engine, since no requirement
so far needs more than that.

### Secret management

- **Local Docker (current and near-term)**: non-sensitive configuration via `.env` files
  (gitignored; `.env.example` committed with placeholder values, per the existing CLAUDE.md
  "never commit secrets" rule, which this ADR operationalizes). Credentials and signing keys
  (DB passwords, RabbitMQ credentials, the JWT private key) via Docker Compose `secrets:`,
  mounted as files rather than environment variables, since environment variables are
  readable via `docker inspect`/`/proc/<pid>/environ` from anything with host or container
  access, while a secrets-mounted file is not.
- **CI**: GitHub Actions encrypted repository/environment secrets, scoped to the workflow
  steps that need them (e.g. a deploy step), never printed to logs.
- **Future cloud deployment**: the provider's secret manager (AWS Secrets Manager / GCP Secret
  Manager / Azure Key Vault / Kubernetes `Secret` backed by one of these via an external-secrets
  operator) injects the same file-path-based secrets at container start — application code
  reads a file path, never an SDK call to a specific provider, so swapping the backing store
  later does not touch application code.
- Secret-scanning (GitGuardian, already installed account-wide per Phase 0 notes) stays a
  required PR check; a secret that reaches a commit is rotated immediately, not just removed
  from the diff, since git history retains it.

### Encryption at rest

Field-level encryption (symmetric, e.g. Django's Fernet-based encrypted model fields) is
applied to specific columns rather than whole-disk/transparent database encryption, because
field-level encryption still protects the data against a SQL-injection dump or an over-broad
ad hoc query — threats whole-disk encryption does nothing against once the database process
itself is running. Fields encrypted at the application layer: customer date of birth, phone
number, and the free-text portion of a saved address (street/unit; city/postal-code-level
geography stays unencrypted since it is needed for branch-matching queries and is not
sensitive on its own). The encryption key is managed through the same secret-management path
above, never embedded in code or committed config. Payment card data is never stored at all
(existing master-prompt rule — PCI DSS tokenization via the payment provider), so it needs no
encryption-at-rest decision here.

### Password hashing

Argon2id, via Django's `Argon2PasswordHasher` listed first in `PASSWORD_HASHERS`. Argon2id is
memory-hard — expensive to crack even with GPU/ASIC parallelism — unlike PBKDF2 (Django's
historical default), which is purely CPU-bound and comparatively cheap to brute-force at scale;
it is also OWASP's current first recommendation for new systems. PBKDF2 stays in the hasher list
only for Django's own built-in compatibility fallback, never as the algorithm new passwords are
hashed with.

### Other OWASP ASVS/Top 10 baseline items fixed now

- **Injection**: all queries go through the ORM/parameterized queries (ADR 0004's Repository
  Pattern is also the SQL-injection boundary); raw SQL string interpolation is disallowed, with
  Bandit/Semgrep enforcing this in Phase 3 CI.
- **CORS**: an explicit per-environment allowlist of frontend origins; no `*` origin is ever
  combined with `Access-Control-Allow-Credentials: true`.
- **Rate limiting**: Redis-backed, per-IP and per-account, applied specifically to
  authentication endpoints (login, refresh, password reset) to blunt credential stuffing and
  brute force, independent of any general API rate limiting added later.
- **Input validation**: DRF serializers are the enforced validation boundary for every
  endpoint; unknown/unexpected fields are rejected, not silently ignored.
- **SSRF**: any outbound HTTP call the backend makes to a URL influenced by user input (e.g. a
  webhook callback URL) validates the target against an allowlist before issuing the request.

## Reason

- Rotate-on-use refresh tokens with family revocation on reuse is what turns "refresh token
  rotation" from a checkbox into an actual stolen-token detector — a plain long-lived refresh
  token that never rotates gives an attacker who steals it the same 14-day window as the
  legitimate user, with no signal that theft occurred.
- `httpOnly`/`Secure`/`SameSite=Strict` cookies for both tokens close the single biggest
  practical JWT mistake (storing tokens in `localStorage`, trivially readable by any XSS
  payload) without adding a second storage mechanism to maintain.
- Putting tenant scope on the `role_assignments` row rather than the user record is required by
  §11's own example (a manager can be scoped to one branch) and naturally extends to a user
  holding the same role at multiple branches without a second data model.
- Field-level encryption, not whole-disk encryption, is the only one of the two that actually
  changes what a SQL-injection or over-broad-query leak exposes — whole-disk encryption is
  orthogonal infrastructure hardening, not a substitute.
- Argon2id's memory-hardness is specifically the property that matters once password hashes
  are ever exposed (e.g. via a backup leak) — a CPU-bound hash like PBKDF2 is far cheaper to
  crack at scale on modern GPU hardware.

## Consequences

- Phase 6's auth baseline implements exactly this JWT/refresh/cookie/CSRF design; Phase 10's
  RBAC implementation builds the `role_assignments` table and the two-step check exactly as
  described, for every one of §11's roles.
- Every module's service layer, not a central gatekeeper alone, is responsible for re-checking
  scope on every operation — a module that skips this check is a security bug, not a missing
  nice-to-have, consistent with ADR 0001's module isolation (nothing central can enforce a
  check a module's own service layer skips).
- A future requirement for admin-editable custom roles/permissions would need a follow-up ADR;
  this ADR deliberately fixes a static seeded role/permission set for now.
- Encrypted fields (date of birth, phone, street address) cannot be queried/filtered directly
  by their plaintext value at the database level — any feature needing to search on these
  fields (none identified yet) would need a separate design, not a plain `WHERE` clause.

## Alternatives

- **Session-based auth (server-side session, session-id cookie) instead of JWT**: rejected —
  master prompt §12 explicitly requires JWT lifecycle and refresh rotation, and a stateless
  access token is a better fit for the eventual-microservice-extraction option in ADR 0001
  (a resource server can verify a JWT with only the public key, no shared session store).
- **Storing the access token in `localStorage` for simpler frontend code**: rejected — this is
  the canonical JWT-plus-XSS vulnerability; the marginal frontend complexity of cookie-based
  auth plus CSRF tokens is a deliberate, well-understood trade for closing that hole.
- **A full dynamic policy engine (e.g. OPA/Casbin) for authorization from day one**: rejected
  for now — every authorization rule described by §11 is expressible as role + organization/
  branch scope; adopting a general policy engine before a rule exists that actually needs one
  would be speculative infrastructure the Phase 10 implementation does not yet have a reason to
  carry.
- **Database-level/whole-disk transparent encryption only, no field-level encryption**:
  rejected — it protects data at rest on a stolen disk but does nothing once the database
  process is running, which is the more realistic threat (injection, an over-permissioned
  query, a leaked backup restored and queried) for this platform's PII fields.
- **bcrypt instead of Argon2id**: considered, not rejected outright as unsafe, but Argon2id is
  OWASP's current first recommendation and is natively supported by Django's hasher list, so it
  is adopted as the primary choice with no compelling reason to prefer bcrypt instead.
