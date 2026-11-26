# Pizza Store Platform

Production-ready event-driven pizza ordering and restaurant management platform built with
Python, Django, Angular, PostgreSQL, MongoDB, Redis, RabbitMQ, Docker and automated CI/CD.

> **Status:** Phase 0 — Repository Foundation. The repository structure and management
> infrastructure are being set up; there is no business code yet. The full roadmap is below.

## Principle

**Infrastructure First → Architecture → Business → Testing → Production.**
No business code is written until the Infrastructure Acceptance Gate (see `docs/architecture/`)
is passed.

## Technology Stack

| Area | Choice |
|---|---|
| Backend | Python, Django, Django REST Framework |
| Backend testing | Pytest, pytest-django, Factory Boy, Faker |
| Frontend | Angular, TypeScript, RxJS, Angular Material |
| Frontend testing | Angular unit/component tests, Playwright E2E |
| DB | PostgreSQL (source of truth), MongoDB (document/audit data), Redis (hot data) |
| Messaging | RabbitMQ (event-driven architecture, Transactional Outbox) |
| Containers | Docker, Docker Compose, Docker Swarm, Kubernetes + Helm |
| Proxy | Nginx |
| CI/CD | GitHub Actions, Renovate, Dependabot |
| Observability | Prometheus, Grafana, Loki, OpenTelemetry/Jaeger |
| Code quality | Ruff, Mypy, Bandit, pip-audit, Semgrep, Trivy, CodeQL, ESLint, Prettier |

**Architecture:** Modular Monolith + Event-Driven Architecture, bounded contexts, Clean
Architecture, DDD, SOLID, Repository Pattern, Service Layer, Dependency Injection.

## Repository structure

```text
pizza-store/
├── backend/          # Django modular monolith (apps separated by domain)
├── frontend/         # Angular monorepo: customer-web/, management-web/, courier-web/
├── infrastructure/   # Docker, Compose, Nginx, Postgres, Mongo, Redis, RabbitMQ, K8s, Swarm, Terraform
├── docs/             # Architecture, ADR, database, messaging, deployment, security, business, API docs
├── scripts/
└── .github/          # Issue/PR templates, workflows, Dependabot/Renovate config
```

Every folder has its own `README.md`.

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready. Only accepts PRs from `test`. |
| `test` | Integration and QA. Feature/infrastructure/bugfix/security/docs branches open PRs here. |
| `preview` | Renovate/Dependabot dependency updates. Never goes directly to `main`. |

Flow: `feature/* → test → main`, `renovate/* → preview → test → main`.

## Local development

```bash
docker compose up -d   # Will activate in Phase 2 — no compose file yet
```

All development runs on Docker; no separate Python/Node/DB installation on the host system.

## Phase roadmap

| # | Phase |
|---|---|
| 0 | Repository Foundation |
| 1 | Research & Architecture |
| 2 | Local Docker Infrastructure |
| 3 | CI/CD & Quality |
| 4 | Observability, Security & Recovery |
| 5 | Testing & Data Infrastructure |
| 6 | Backend Foundation |
| 7 | Frontend Foundation |
| 8 | Deployment Infrastructure |
| 9 | Infrastructure Acceptance Gate |
| 10 | Core Business |
| 11 | Ordering & Payment |
| 12 | Kitchen, Inventory & Delivery |
| 13 | Loyalty, Marketing & Management |
| 14 | Advanced Features |
| 15 | Production Readiness |

Business code only starts after Phase 9 (Infrastructure Acceptance Gate) is complete.

## Documentation

Complete technical documentation lives in the `docs/` folder: architecture, ADR, database,
messaging, deployment, security, business, API, testing, operations, runbooks.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
