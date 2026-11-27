import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from django.db import IntegrityError, transaction

from shared.idempotency.models import IdempotencyKey


def fingerprint(request_payload: object) -> str:
    """Deterministic sha256 hex digest of a JSON-serializable request body, used to detect
    the same `Idempotency-Key` reused with a different payload."""

    normalized = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


class IdempotencyConflictError(Exception):
    """The same (key, scope) was already used with a different request body."""


class IdempotencyKeyOwnershipError(Exception):
    """The same (key, scope) was already used by a different user."""


@dataclass(frozen=True)
class IdempotentResponse:
    status: int
    body: object
    replayed: bool


class IdempotencyService:
    """Called by `shared.idempotency.drf.IdempotentActionMixin`, or directly by a non-DRF
    caller. `handler` returns the `(status, body)` pair to cache for a successful or a
    deliberate business-level outcome the caller wants replayed verbatim on retry; if
    `handler` raises instead, the attempt is rolled back and nothing is cached, so the client
    is free to retry the request from scratch -- only an outcome `handler` itself returns is
    ever treated as "the" answer for this key.
    """

    def run_once(
        self,
        *,
        key: str,
        scope: str,
        user_id: int,
        request_payload: object,
        handler: Callable[[], tuple[int, object]],
    ) -> IdempotentResponse:
        request_fingerprint = fingerprint(request_payload)

        existing = self._find(key, scope)
        if existing is not None:
            return self._resolve_existing(existing, user_id, request_fingerprint)

        try:
            with transaction.atomic():
                response_status, response_body = handler()
                IdempotencyKey.objects.create(
                    key=key,
                    scope=scope,
                    user_id=user_id,
                    request_fingerprint=request_fingerprint,
                    response_status=response_status,
                    response_body=response_body,
                )
        except IntegrityError:
            # Lost a race with a concurrent request using the same (key, scope) -- handler's
            # writes above were rolled back by the atomic block; the winner's row is now
            # committed, so replay it instead of re-raising.
            existing = self._find(key, scope)
            if existing is None:
                raise
            return self._resolve_existing(existing, user_id, request_fingerprint)

        return IdempotentResponse(status=response_status, body=response_body, replayed=False)

    @staticmethod
    def _find(key: str, scope: str) -> IdempotencyKey | None:
        return IdempotencyKey.objects.filter(key=key, scope=scope).first()

    @staticmethod
    def _resolve_existing(
        existing: IdempotencyKey, user_id: int, request_fingerprint: str
    ) -> IdempotentResponse:
        if existing.user_id != user_id:
            raise IdempotencyKeyOwnershipError(
                f"Idempotency key scope={existing.scope!r} belongs to a different user."
            )
        if existing.request_fingerprint != request_fingerprint:
            raise IdempotencyConflictError(
                f"Idempotency key scope={existing.scope!r} was already used with a "
                "different request body."
            )
        return IdempotentResponse(
            status=existing.response_status, body=existing.response_body, replayed=True
        )
