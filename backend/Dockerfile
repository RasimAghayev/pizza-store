# Base image pinned to the same Python version already used by
# .github/workflows/quality-gate.yml's backend-quality job, for consistency between CI and
# the real Compose service this Dockerfile builds (Issue #126, Phase 6).
FROM python:3.15-slim AS base

# curl is needed by this image's own Compose healthcheck (infrastructure/compose/
# docker-compose.yml's backend service) -- python:3.15-slim ships neither curl nor wget.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
