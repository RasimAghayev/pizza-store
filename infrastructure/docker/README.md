# Docker

Multi-stage Dockerfiles, non-root user per service, healthchecks, resource limits.

> Status: Phase 2 — the Compose stack (`infrastructure/compose/`) uses official images for
> every Phase 2 service (PostgreSQL, MongoDB, Redis, RabbitMQ, Nginx); custom multi-stage
> Dockerfiles are needed starting Phase 6 for the backend/frontend containers.
