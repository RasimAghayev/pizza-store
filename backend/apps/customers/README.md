# Customers

Owns the customer bounded context: the `Customer` profile row (`user_id, created_at,
consent_personal_data_at`) and self-registration (Issue #176). Profile fields (name/phone/DOB)
and saved addresses are Issue #179's job, not this one.

`RegistrationService.register(email, password) -> Customer` calls
`apps.identity.services.registration_service.RegistrationService.register()` -- see
`backend/apps/identity/README.md`'s "inbound calls" section; `identity.User`/credential
creation is `identity`'s exclusive domain (ADR 0004), so this module never constructs a
`User` row itself or imports `identity.models`/`repositories`. It then creates the `Customer`
row, calls `identity.services.role_assignment_service.RoleAssignmentService.assign()` (Issue
#175) to grant the `customer` role, and publishes `CustomerRegistered` -- all inside the same
DB transaction, so the user/customer/role-assignment/event rows are all-or-nothing.

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
(`docs/api/conventions.md`), not a 500.

Publishes: `CustomerRegistered` (`customers.events` / `customer.registered.v1`).
