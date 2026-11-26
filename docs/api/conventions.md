# API Conventions

> Status: Phase 6 (Issues #128, #129) — Django REST Framework + drf-spectacular configured,
> applied against a real endpoint, and extended with the JWT/refresh-token authentication
> baseline. Every later module's API follows these conventions.

## Versioning

URL-path versioning (DRF's `URLPathVersioning`), e.g. `GET /api/v1/orders/`. Every module's
`api/urls.py` is mounted under `api/<version>/<module>/...` in `backend/config/urls.py`.

```python
REST_FRAMEWORK = {
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
}
```

Chosen over header (`AcceptHeaderVersioning`) or query-parameter (`QueryParameterVersioning`)
versioning because it is the simplest to curl, cache, and test explicitly — the version is
visible in the URL itself, requires no special client headers, and plays well with HTTP
caching and browser-based exploration (Swagger UI, `curl`, bookmarked links).

A request for a version outside `ALLOWED_VERSIONS` (e.g. `GET /api/v2/ping/` today) returns
a 404 with the standard error envelope (`code: "not_found"`), not a silent fallback to `v1`.

Not versioned: `GET /health/` (a Compose-level liveness probe predating this convention, kept
intentionally outside it — see Issue #128) and the schema/docs meta-endpoints below.

## Error envelope

Every 4xx/5xx response from a DRF view — including DRF's own `ValidationError`, `NotFound`,
`PermissionDenied`, `AuthenticationFailed`/`NotAuthenticated`, and any unhandled exception —
is shaped by a single custom `EXCEPTION_HANDLER`
(`backend/shared/api/exception_handler.py::api_exception_handler`):

```json
{
  "error": {
    "code": "validation_error",
    "message": "Validation failed.",
    "details": {}
  }
}
```

Fixed code taxonomy for now (extend deliberately, not ad hoc, as new cases arise):

| HTTP status | `code`                 |
|-------------|------------------------|
| 400         | `validation_error`     |
| 401         | `authentication_failed`|
| 403         | `permission_denied`    |
| 404         | `not_found`            |
| 5xx         | `internal_error`       |

`details` carries structured, field-level information when available (e.g. a serializer's
per-field validation errors); it is `{}` when the error is a single flat message (e.g. "Not
found."). For `internal_error`, `message` is always the fixed generic string above — the real
exception and its traceback are logged server-side only and never reach the client, including
when `DEBUG=False` (verified by a dedicated test).

## Schema and docs

- `GET /api/schema/` — the generated OpenAPI 3 document (drf-spectacular).
- `GET /api/docs/` — Swagger UI rendering that document.

## Conventions-proof endpoint

`GET /api/v1/ping/` (`backend/shared/api/views.py::PingView`) is a minimal, explicitly-labeled
endpoint returning `{"message": "pong"}`. It exists only to prove the three conventions above
against something real — URL-path versioning, OpenAPI schema generation, and the error
envelope all have at least one real endpoint exercising them, not just unused configuration.
It is not a product endpoint; later modules do not depend on it.

## Authentication (Issue #129, ADR 0006)

`POST /api/v1/auth/{login,refresh,logout}` (`backend/apps/identity/api/`) issue and rotate
the two tokens every other authenticated endpoint will rely on: a short-lived RS256 JWT
access token (15 min) and an opaque, rotate-on-use refresh token (14 days, only its SHA-256
hash persisted).

### `X-Client-Type` header

Every auth request must send `X-Client-Type: browser` or `X-Client-Type: native`; its
absence or any other value is a 400. The two client types are handed tokens differently
(ADR 0006):

| Client type | Access/refresh token delivery                                    |
|-------------|-------------------------------------------------------------------|
| `browser`   | httpOnly, `Secure`, `SameSite=Strict` cookies (`access_token`, `refresh_token`) |
| `native`    | Both tokens in the JSON response/request body                    |

### CSRF scoping

DRF's `APIView.as_view()` wraps every view in `csrf_exempt` unconditionally, so
`CsrfViewMiddleware` never enforces CSRF on its own for any DRF view. For `browser`-mode
requests, `shared/api/csrf.py::enforce_csrf` is called explicitly to re-enable the
`X-CSRFToken` double-submit check — but only on `refresh` and `logout`, not `login`:

- **`login` is exempt.** No session/cookie exists yet for an attacker to forge at this point
  — the request carries only a candidate email/password, which CSRF protection does not
  apply to. The response seeds the CSRF cookie (`django.middleware.csrf.get_token`) that the
  *next* cookie-authenticated call will need.
- **`refresh` and `logout` enforce it.** Both are cookie-authenticated, state-changing
  requests once a browser session exists, which is exactly what CSRF protection is for.

### Rate limiting

Redis-backed (`django_redis`, `CACHES["default"]`), via DRF's `ScopedRateThrottle`/
`SimpleRateThrottle` (`backend/apps/identity/api/throttling.py`):

| Scope          | Rate   | Keyed by                          | Applies to      |
|----------------|--------|------------------------------------|-----------------|
| `login`        | 10/min | client IP                          | `POST /login/`  |
| `login_account`| 5/min  | submitted email (independent of IP)| `POST /login/`  |
| `refresh`      | 30/min | client IP                          | `POST /refresh/`|

`login_account` exists alongside the per-IP `login` throttle specifically to cap credential
stuffing against one account even when attempts are spread across many source IPs.

### Known limitation: `SameSite=Strict` vs. cross-origin CORS

ADR 0006 specifies both `SameSite=Strict` cookies and a CORS origin allowlist for browser
clients. These two controls are in tension for as long as the frontend and backend are
served from different origins (the current topology — see the `backend` service's `data-net`
comment in `infrastructure/compose/docker-compose.yml`): `SameSite=Strict` blocks the browser
from attaching the cookie to *any* cross-site request, including a same-site-unaware
`fetch()` from a separate frontend origin, regardless of what CORS allows. Implemented here
exactly as ADR 0006 specifies, per this repository's "implement as specified, flag
deviations" convention — full browser-mode, cookie-authenticated cross-origin testing is
only meaningful once the frontend and backend share an origin (e.g. behind the planned Nginx
edge). Until then, treat `browser`-mode auth as implemented-but-not-yet-exercisable
end-to-end in a real cross-origin browser session; the `native`-mode path has no such
limitation and is fully covered by `backend/apps/identity/tests/integration/test_auth.py`.
