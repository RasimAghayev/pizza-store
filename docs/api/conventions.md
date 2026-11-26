# API Conventions

> Status: Phase 6 (Issue #128) — Django REST Framework + drf-spectacular configured and
> applied against a real endpoint. Every later module's API follows these conventions.

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
