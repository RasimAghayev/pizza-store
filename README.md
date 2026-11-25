# Pizza Store Platform

Production-ready event-driven pizza ordering and restaurant management platform built with
Python, Django, Angular, PostgreSQL, MongoDB, Redis, RabbitMQ, Docker and automated CI/CD.

> **Status:** Phase 0 — Repository Foundation. Repository strukturu və idarəetmə
> infrastrukturu qurulur; hələ biznes kodu yoxdur. Tam yol xəritəsi aşağıdadır.

## Prinsip

**Infrastructure First → Architecture → Business → Testing → Production.**
İnfrastruktur Acceptance Gate-dən (bax `docs/architecture/`) keçmədən biznes kodu yazılmır.

## Texnologiya Stack

| Sahə | Seçim |
|---|---|
| Backend | Python, Django, Django REST Framework |
| Backend test | Pytest, pytest-django, Factory Boy, Faker |
| Frontend | Angular, TypeScript, RxJS, Angular Material |
| Frontend test | Angular unit/component testləri, Playwright E2E |
| DB | PostgreSQL (source of truth), MongoDB (document/audit data), Redis (hot data) |
| Messaging | RabbitMQ (event-driven architecture, Transactional Outbox) |
| Containers | Docker, Docker Compose, Docker Swarm, Kubernetes + Helm |
| Proxy | Nginx |
| CI/CD | GitHub Actions, Renovate, Dependabot |
| Observability | Prometheus, Grafana, Loki, OpenTelemetry/Jaeger |
| Kod keyfiyyəti | Ruff, Mypy, Bandit, pip-audit, Semgrep, Trivy, CodeQL, ESLint, Prettier |

**Arxitektura:** Modular Monolith + Event-Driven Architecture, bounded contexts, Clean
Architecture, DDD, SOLID, Repository Pattern, Service Layer, Dependency Injection.

## Repository strukturu

```text
pizza-store/
├── backend/          # Django modular monolith (domain-lərə görə ayrılmış app-lar)
├── frontend/         # Angular monorepo: customer-web/, management-web/, courier-web/
├── infrastructure/   # Docker, Compose, Nginx, Postgres, Mongo, Redis, RabbitMQ, K8s, Swarm, Terraform
├── docs/             # Architecture, ADR, database, messaging, deployment, security, business, API docs
├── scripts/
└── .github/          # Issue/PR templates, workflows, Dependabot/Renovate config
```

Hər qovluğun öz `README.md`-si mövcuddur.

## Branch strategiyası

| Branch | Məqsəd |
|---|---|
| `main` | Production-ready. Yalnız `test`-dən PR qəbul edir. |
| `test` | İnteqrasiya və QA. Feature/infrastructure/bugfix/security/docs branch-ləri bura açılır. |
| `preview` | Renovate/Dependabot dependency yeniləmələri. Heç vaxt birbaşa `main`-ə getmir. |

Axın: `feature/* → test → main`, `renovate/* → preview → test → main`.

## Local development

```bash
docker compose up -d   # Phase 2-də aktivləşəcək — hələ compose faylı yoxdur
```

Bütün inkişaf Docker üzərində aparılır; host sistemdə ayrıca Python/Node/DB quraşdırılmır.

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

Biznes kodu yalnız Phase 9 (Infrastructure Acceptance Gate) tamamlandıqdan sonra başlayır.

## Documentation

Tam texniki sənədləşmə `docs/` qovluğundadır: architecture, ADR, database, messaging,
deployment, security, business, API, testing, operations, runbooks.

## Contributing

Bax [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
