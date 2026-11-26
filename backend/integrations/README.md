# Integrations

Reserved for a module's explicit, sparingly-used synchronous call into another module's
`services/` entry point, per
[ADR 0004](../../docs/adr/0004-backend-module-and-frontend-feature-layout.md)'s exception to
the default event-driven (RabbitMQ) communication between modules — e.g. pricing needing a
product's current active price in the same request.

Genuinely empty until a real cross-module synchronous read is needed; no placeholder code is
added speculatively. When a module does add one, it must also name the link in its own
`README.md` per the cross-file dependency comment convention (`CLAUDE.md`).
