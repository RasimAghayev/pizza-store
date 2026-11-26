import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRETS_DIR = Path(os.environ.get("DJANGO_SECRETS_DIR", "/run/secrets"))


def _read_secret(name: str, default: str | None = None) -> str | None:
    """Reads a Compose secret file (ADR 0006); falls back to `default` when run outside
    Compose (e.g. a one-off local `manage.py` command)."""
    path = SECRETS_DIR / name
    if path.is_file():
        return path.read_text().strip()
    return default


SECRET_KEY = _read_secret("django_secret_key", "insecure-local-dev-key-do-not-use-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [
    h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h
]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.identity",
    "health",
]

# identity.User (Issue #127) replaces Django's default auth.User -- see
# backend/apps/identity/models/user.py.
AUTH_USER_MODEL = "identity.User"

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Postgres password comes from the `postgres_password` Compose secret (ADR 0006), the same
# one every other service in infrastructure/compose/docker-compose.yml already reads --
# falls back to the POSTGRES_PASSWORD env var outside Compose (e.g. CI's job-level service
# container in quality-gate.yml, which has no secrets: mount).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "pizza_store"),
        "USER": os.environ.get("POSTGRES_USER", "pizza_store"),
        "PASSWORD": _read_secret("postgres_password", os.environ.get("POSTGRES_PASSWORD", "")),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
