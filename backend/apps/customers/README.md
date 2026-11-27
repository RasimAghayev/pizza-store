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
same DB transaction, so the user/customer/role-assignment/event rows are all-or-nothing. The
create-`Customer`/assign-role/publish-event half of that is factored out as its own public
`RegistrationService.provision_customer(user) -> Customer` (Issue #178) -- idempotent (a
second call for a `user` that already has a `Customer` row is a no-op, returning the existing
row) -- so `apps.identity.services.social_login_service.SocialLoginService` can call it
unconditionally on every social login for a `User` that already exists (not just a brand-new
one), without duplicating this module's own provisioning logic. This is called **from**
`identity`, the reverse of every other cross-module call documented in this file -- see
`backend/apps/identity/README.md`'s social login section for why: `identity` owns the social
login use case end to end and reaches into `customers` for the profile it provisions, the same
direction `LoginView`'s own callers never need because email/password registration already
starts on the `customers` side.

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
`POST /api/v1/customers/me/profile/consent/`, `GET/POST /api/v1/customers/me/addresses/`, and
`GET/PATCH/DELETE /api/v1/customers/me/addresses/<id>/` -- all ownership-only
(`IsAuthenticated`, scoped to `request.user`'s own `Customer` row), no RBAC scope needed since
this isn't a staff/branch concern.

`services/verification_service.py::VerificationService` (Issue #177) handles email/phone OTP
verification: `request_email_verification`/`confirm_email_verification` and
`request_phone_verification`/`confirm_phone_verification` generate a 6-digit code
(`domain/otp.py`, pure domain logic, no Django import), store only its SHA-256 hash in the
Redis cache keyed `otp:{purpose}:{user_id}` with a 5-minute TTL
(`docs/database/redis-caching-and-ttl-policy.md`), and delete that key explicitly on successful
confirmation so a code can never be replayed even within its TTL window. Requesting phone
verification before a phone number exists on the customer's profile raises
`PhoneNotOnFileError` (`400 validation_error`). Delivery goes through
`services/notification_gateway.py::NotificationGateway` -- `LoggingNotificationGateway` is the
only implementation until a real email/SMS provider is chosen as its own Task (architecture
risk register's "Likely Technical Debt #2", mirroring the accepted precedent for the Payment
Gateway Abstraction): email is real via Django's console backend
(`shared/notifications/console_gateway.py`), SMS only logs. Once both `email_verified_at` and
`phone_verified_at` (nullable `Customer` columns) are set, the customer is granted the
`verified_customer` role via
`identity.services.role_assignment_service.RoleAssignmentService.assign()` (idempotent --
checked first via `roles_for()`), per Issue #177's dual-channel gating requirement.
`api/` exposes `POST /api/v1/customers/verify/email/request/`,
`POST /api/v1/customers/verify/email/confirm/`, `POST /api/v1/customers/verify/phone/request/`,
and `POST /api/v1/customers/verify/phone/confirm/`, all `IsAuthenticated`, throttled via
`shared/api/throttling.py::OtpRequestRateThrottle`/`OtpConfirmRateThrottle` (not
`identity.api.throttling` -- that would be a `customers -> identity.api` cross-layer import,
disallowed by ADR 0004; the throttle classes live in `shared/` precisely so both modules can
use them without either importing the other's API layer).

Publishes: `CustomerRegistered` (`customers.events` / `customer.registered.v1`).
