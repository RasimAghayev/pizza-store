# Role / Permission Matrix

Every role from master prompt §11, against the permissions it actually holds as of Phase 10
(Core Business). Generated from, and must be kept in sync with,
[`backend/apps/identity/domain/rbac.py`](../../backend/apps/identity/domain/rbac.py)'s
`ROLE_PERMISSIONS` mapping — that file is the source of truth; this document is a human-
readable projection of it, per Epic #14's Documentation Requirements (Issue #183).

A permission string is `<module>.<action>`; `view` governs read access to a staff-only
resource (or the staff-only variant of a resource that also has a public read path — see
[ADR 0006](../adr/0006-security-architecture-baseline.md)), `edit` governs create/update/
delete. Every write is additionally re-scoped per-request by
[`shared/permissions/base.py::TwoStepPermission`](../../backend/shared/permissions/base.py):
holding a permission is necessary but not sufficient — the specific resource acted on must
also fall within one of the role's actual `RoleAssignment` scopes (organization-wide,
branch-specific, or unscoped for Super Admin). See
[`shared/tests/integration/test_multi_tenant_isolation.py`](../../backend/shared/tests/integration/test_multi_tenant_isolation.py)
for the end-to-end proof of that second check across every module below.

## Customer-facing roles

These are progressive account states (set by `customers`/`identity` services as the customer
verifies their email/phone — Issue #177), never an assignable staff role, and carry no scope
(`organization_id`/`branch_id` are always `null` on their `RoleAssignment` row). None of them
hold any permission string below — the customer-facing API surface
(`apps/customers/api/`) is ownership-scoped to the requesting customer's own row, not
RBAC-gated.

| Role | Granted when | Permissions |
|---|---|---|
| **Guest** | Never stored — the absence of any `RoleAssignment` row for a request with no/invalid credentials. | none |
| **Customer** | Registration completes (`CustomerRegistrationView`, Issue #176). | none |
| **Verified Customer** | Both `email_verified_at` and `phone_verified_at` are set (Issue #177). | none |
| **Loyalty Member** | Reserved for Phase 13 (Loyalty, Marketing & Management) — not yet granted by any Phase 10 code path. | none |

## Staff roles — organization-scoped

`organization_id` set, `branch_id` null on the `RoleAssignment` row — the grant covers every
branch under that organization (or, for Super Admin, every organization).

| Role | `identity` | `restaurants` | `branches` | `products` | `menu` |
|---|---|---|---|---|---|
| **Super Admin** | manage_roles | view, edit | view, edit | view, edit | view, edit |
| **Organization Owner** | manage_roles | view, edit | view, edit | view, edit | view, edit |
| **Accountant** | — | view | view | view | view |
| **Marketing Manager** | — | view | view | view | view |

Super Admin is additionally unscoped (no `organization_id`/`branch_id` at all), so it matches
every resource regardless of tenant — the only role for which that's true.

## Staff roles — branch-scoped

`branch_id` set, `organization_id` null — the grant covers exactly that one branch. A
branch-scoped assignment can never satisfy an organization-wide resource's scope check (e.g.
creating a new `Organization`/`Restaurant`, or editing a `Product`/`MenuCategory`, both of
which have no branch dimension of their own) — see `ROLE_PERMISSIONS`' own inline comments in
`rbac.py` for why that's structural, not a separate rule to maintain.

| Role | `restaurants` | `branches` | `products` | `menu` |
|---|---|---|---|---|
| **Restaurant Manager** | view | view, edit | view | view, edit |
| **Branch Manager** | view | view, edit | view | view, edit |
| **Cashier** | — | view | view | view |
| **Kitchen Manager** | — | view | view | view |
| **Kitchen Staff** | — | view | view | view |
| **Delivery Manager** | — | view | view | view |
| **Courier** | — | view | view | view |
| **Inventory Manager** | — | view | view | view |
| **Customer Support** | — | view | view | view |

Restaurant Manager and Branch Manager hold identical permission sets today — both are
branch-scoped, and nothing in Phase 10 yet distinguishes "manages one restaurant's several
branches" from "manages one branch" at the permission-string level (their `RoleAssignment`
rows differ in which/how many branches are actually assigned, not in what the role can do to
each one it holds). A future phase that needs to tell them apart does so by adding a new
permission string, not by changing this table's shape.

## Modules with no permissions yet

`customers` has no RBAC-gated staff endpoint (ownership-scoped only, see above) and no
`customers.*` permission string exists. Every module from Phase 11 onward (`pricing`, `cart`,
`orders`, `payments`, `kitchen`, `inventory`, `couriers`, `delivery`, `loyalty`,
`notifications`, `reviews`, `analytics`, `audit`) will append its own permission strings to
the relevant roles' sets in `ROLE_PERMISSIONS` when that module is built, per `rbac.py`'s own
documented convention of not speculating about permissions for modules that don't exist yet.
Update this table in the same PR that adds each module's permissions, so it never drifts from
`ROLE_PERMISSIONS` the way Issue #183's audit found `docs/adr/0004-...`'s own CI-wiring claim
had drifted from reality.
