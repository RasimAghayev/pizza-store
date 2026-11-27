# Customers

Owns the customer bounded context: the `Customer` profile row (`user_id, created_at,
consent_personal_data_at, first_name, last_name, phone, date_of_birth`), saved `Address`
rows, and self-registration (Issue #176).

`phone`/`date_of_birth` (on `Customer`) and `street_and_unit` (on `Address`) are encrypted at
rest via `shared/encryption/fields.py::EncryptedCharField`/`EncryptedDateField` (ADR 0006,
Issue #179) -- a thin Fernet-based field built on the existing `cryptography` dependency
rather than `django-cryptography`, which has had no release supporting Django 6 and no commit
in years (checked at implementation time, per the research-before-implementing rule). The key
is sourced from the `field_encryption_key` Compose secret (`make
generate-field-encryption-key`), falling back to an ephemeral, process-local key when that
secret is absent -- the same pattern `apps/identity/services/token_service.py` uses for the
JWT signing key. `city`/`postal_code` on `Address` stay plaintext: they're needed for
branch-matching queries and aren't sensitive alone. `latitude`/`longitude` are nullable --
master prompt section 11 requires a manually-entered/map-picked address with no GPS
coordinates to be just as valid as a GPS-derived one.

`date_of_birth` additionally requires `consent_personal_data_at` to already be set --
`services/profile_service.py::ProfileService.update_profile` rejects it otherwise
(`ConsentRequiredError`); `ProfileService.record_consent` is the only way to set that
timestamp, exposed as its own `POST .../consent/` action rather than an ordinary profile
field edit, since consent is a one-way, auditable event.

`services/address_service.py::AddressService` enforces "exactly one default address per
customer" itself (not just a DB constraint): setting a new default clears every other one
inside the same transaction. Every address lookup is scoped to the requesting customer's own
`Customer` row; an id that exists but belongs to someone else returns 404, never 403, so a
request can't distinguish "not yours" from "doesn't exist".

`RegistrationService.register(email, password) -> Customer` calls
`apps.identity.services.registration_service.RegistrationService.register()` -- see
`backend/apps/identity/README.md`'s "inbound calls" section; `identity.User`/credential
creation is `identity`'s exclusive domain (ADR 0004), so this module never constructs a
`User` row itself or imports `identity.models`/`repositories`. It then creates the `Customer`
row, calls `identity.services.role_assignment_service.RoleAssignmentService.assign()` (see
Issue #175) to grant the `customer` role, and publishes `CustomerRegistered` -- all inside the
same DB transaction, so the user/customer/role-assignment/event rows are all-or-nothing.

`CustomerOutboxEvent` (`models/customer_outbox_event.py`) is this module's concrete
`shared/events/outbox.py::AbstractOutboxEvent` subclass, relayed to the `customers.events`
topic exchange by `manage.py relay_outbox --model customers.CustomerOutboxEvent --exchange
customers.events` (ADR 0005). `CustomerRegistered` (`events/customer_registered.py`) is the
first real event ever published through the Phase 6 Outbox infrastructure --
`docs/messaging/event-catalog.md`'s `customers.events` exchange moved from a naming
reservation to a live, durable exchange when this Task shipped.

`CustomerRepository` is the only file in this module allowed to issue an ORM query, per
ADR 0004.

`api/` exposes `POST /api/v1/customers/register/` -- email/password in, `201 {"id": <customer
id>}` out; a duplicate email returns the standard `validation_error` envelope
(`docs/api/conventions.md`), not a 500. Also `GET/PATCH /api/v1/customers/me/profile/`,
`POST /api/v1/customers/me/profile/consent/`, and `GET/POST /api/v1/customers/me/addresses/`
+ `GET/PATCH/DELETE /api/v1/customers/me/addresses/<id>/` -- all ownership-only
(`IsAuthenticated`, scoped to `request.user`'s own `Customer` row), no RBAC scope needed since
this isn't a staff/branch concern.

Publishes: `CustomerRegistered` (`customers.events` / `customer.registered.v1`).
