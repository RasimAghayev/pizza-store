.PHONY: up down build restart logs status health test test-backend test-frontend lint migrate seed reset clean \
	dataset-smoke dataset-integration dataset-load generate-jwt-keypair generate-field-encryption-key

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
	$(COMPOSE) exec backend pytest

test-frontend:
	$(COMPOSE) exec frontend npm test

lint:
	$(COMPOSE) exec backend ruff check .
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

# Synthetic dataset generator (Task #111/#112) is a standalone Python + Faker script with
# no Django dependency and no Compose service of its own -- it runs directly on the host,
# not through $(COMPOSE) exec, by design (see scripts/dataset/README.md).
dataset-smoke:
	python scripts/dataset/generate.py --tier smoke --verify

dataset-integration:
	python scripts/dataset/generate.py --tier integration --verify

dataset-load:
	python scripts/dataset/generate.py --tier load --verify

# RS256 JWT signing keypair (ADR 0006, Issue #129) -- run once per environment; refuses to
# overwrite an existing key by default, since that would invalidate every live refresh token.
generate-jwt-keypair:
	python scripts/generate-jwt-keypair.py

# Fernet field-level encryption key (ADR 0006, Issue #179) -- run once per environment;
# refuses to overwrite an existing key by default, since that would make every
# already-encrypted row (DOB/phone/street address) unreadable.
generate-field-encryption-key:
	python scripts/generate-field-encryption-key.py
