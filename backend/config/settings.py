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
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.identity",
    "apps.customers",
    "apps.restaurants",
    "apps.branches",
    "apps.products",
    "apps.menu",
    "health",
    # Registered as an app (zero concrete models of its own) purely so Django's
    # management-command discovery finds shared/management/commands/relay_outbox.py
    # (Issue #130) -- see that file.
    "shared",
]

# identity.User (Issue #127) replaces Django's default auth.User -- see
# backend/apps/identity/models/user.py.
AUTH_USER_MODEL = "identity.User"

# Argon2id first (ADR 0006) -- PBKDF2 stays only as a read-compatibility fallback for
# password hashes, never used to hash a new password.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

MIDDLEWARE = [
    # Must run before CommonMiddleware per django-cors-headers' own setup docs.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # DRF's APIView exempts every view from this middleware's own enforcement
    # (rest_framework.views.APIView.as_view wraps every view in csrf_exempt); kept in
    # MIDDLEWARE so it still sets the CSRF cookie on responses that call
    # django.middleware.csrf.get_token(). Actual enforcement for cookie-authenticated
    # requests is done explicitly via shared/api/csrf.py::enforce_csrf -- see ADR 0006.
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# Required for drf-spectacular's Swagger UI (/api/docs/, Issue #128) to render its own
# packaged template -- APP_DIRS discovers it without this app needing to ship its own
# templates/ dir. context_processors is limited to what MIDDLEWARE/INSTALLED_APPS actually
# support here: no session/auth/messages middleware is installed, so the auth/messages
# processors are deliberately omitted rather than referencing machinery that doesn't exist.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

# CORS (ADR 0006): an explicit origin allowlist, never combined with a wildcard; credentials
# are required since browser clients authenticate via cookies, not an Authorization header.
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",") if o
]
CORS_ALLOW_CREDENTIALS = True

# The CSRF cookie carries the same policy as the access/refresh cookies (ADR 0006) except
# httponly -- the frontend must read this cookie's value to send it back as X-CSRFToken.
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"

# API conventions (Issue #128): URL-path versioning + a shared error envelope applied via a
# custom EXCEPTION_HANDLER -- see shared/api/exception_handler.py and docs/api/conventions.md.
# Throttle scopes (Issue #129, ADR 0006) are applied per-view in apps/identity/api/views.py;
# rates documented in docs/api/conventions.md.
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "EXCEPTION_HANDLER": "shared.api.exception_handler.api_exception_handler",
    # Resolves request.user from the access token (cookie or Authorization header) for every
    # protected endpoint from Issue #175 onward -- login/refresh/logout/ping stay public by
    # explicitly setting authentication_classes = [] (ADR 0006; see apps/identity/api/views.py).
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.api.authentication.JWTCookieOrHeaderAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "login_account": "5/min",
        "refresh": "30/min",
        # DRF's rate-string parser only resolves whole second/minute/hour/day windows (its
        # SimpleRateThrottle.parse_rate reads just period[0]) -- a literal "3/10min" per the
        # Issue's own example text is unparseable. Approximated to an hourly window
        # preserving the same request density (Issue #177, ADR 0006).
        "otp_request": "18/hour",
        "otp_confirm": "30/hour",
        "password_reset_request": "18/hour",
        "password_reset_confirm": "30/hour",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Pizza Store API",
    "DESCRIPTION": "Pizza Store Platform backend API.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

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

# Redis-backed cache (ADR 0006), used today by DRF's ScopedRateThrottle on the identity
# module's login/refresh endpoints -- a per-process in-memory cache would not share throttle
# counters across workers. Same `redis_password` Compose secret the `redis` service itself
# reads; falls back to the REDIS_PASSWORD env var outside Compose.
_REDIS_PASSWORD = _read_secret("redis_password", os.environ.get("REDIS_PASSWORD", ""))
_REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
_REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{_REDIS_PASSWORD}@{_REDIS_HOST}:{_REDIS_PORT}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

# RabbitMQ (ADR 0005, Issue #130) -- same Compose-secret-file-first pattern as
# postgres/redis above. Read by shared/events/publisher.py::connection_parameters; falls
# back to the guest/guest default outside Compose (e.g. CI's job-level service container in
# quality-gate.yml, which has no secrets: mount and relies on RabbitMQ's own loopback-only
# guest-user allowance).
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = _read_secret("rabbitmq_password", os.environ.get("RABBITMQ_PASSWORD", "guest"))

# RS256 JWT signing key (ADR 0006, Issue #129) -- read by
# apps/identity/services/token_service.py, which falls back to an ephemeral, process-local
# keypair when this is unset (e.g. a lightweight test/CI run outside Compose). Generated via
# scripts/generate-jwt-keypair.py; see docs/security/secret-management.md.
JWT_PRIVATE_KEY_PEM = _read_secret("jwt_private_key")

# Fernet field-level encryption key (ADR 0006, Issue #179) -- read by
# shared/encryption/fields.py, which falls back to an ephemeral, process-local key when this
# is unset (e.g. a lightweight test/CI run outside Compose), same pattern as
# JWT_PRIVATE_KEY_PEM above. Generated via scripts/generate-field-encryption-key.py; see
# docs/security/secret-management.md.
FIELD_ENCRYPTION_KEY = _read_secret("field_encryption_key")

# No real email/SMS provider has been chosen yet (architecture risk register's "Likely
# Technical Debt #2") -- Issue #177 deliberately implements OTP/password-reset delivery
# against Django's own console backend only; a real provider is a separate, later Task. See
# shared/notifications/console_gateway.py.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@pizza-store.example"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
