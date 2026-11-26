.PHONY: up down build restart logs status health test test-backend test-frontend lint migrate seed reset clean

# NOTE: targets below assume infrastructure/compose/docker-compose.yml, added in Phase 2
# (Local Docker Infrastructure). Running them before that file exists will fail.
#
# --env-file .env is required because Compose otherwise looks for .env next to the compose
# file (infrastructure/compose/), not at the repo root where .env.example documents it.

COMPOSE := docker compose -f infrastructure/compose/docker-compose.yml --env-file .env

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

restart: down up

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

health:
	$(COMPOSE) ps --format '{{.Name}}: {{.Status}}'

test: test-backend test-frontend

test-backend:
	cd backend && pytest

test-frontend:
	$(COMPOSE) exec frontend npm test

lint:
	cd backend && ruff check .
	$(COMPOSE) exec frontend npm run lint

migrate:
	$(COMPOSE) exec backend python manage.py migrate

seed:
	$(COMPOSE) exec backend python manage.py seed

reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d

clean:
	$(COMPOSE) down -v --remove-orphans
