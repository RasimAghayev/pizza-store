from collections.abc import Callable

from rest_framework import exceptions
from rest_framework.request import Request
from rest_framework.response import Response

from shared.idempotency.service import (
    IdempotencyConflictError,
    IdempotencyKeyOwnershipError,
    IdempotencyService,
)


class IdempotencyConflict(exceptions.APIException):
    status_code = 409
    default_detail = "This Idempotency-Key was already used with a different request body."
    default_code = "conflict"


class IdempotentActionMixin:
    """Opt-in per view/action -- see shared/idempotency/service.py for the underlying
    mechanism this wraps. A view calls `self.perform_idempotent(scope=..., handler=...)` from
    inside its own action method instead of running its side effect directly. The
    `Idempotency-Key` request header is optional: when the client sends none, `handler` just
    runs normally with no duplicate-request protection -- callers that must always require the
    header (e.g. checkout, Issue #197) enforce that themselves before calling this. Assumes
    the view already requires an authenticated user (`request.user.id` is used as the cache
    owner)."""

    # Declares the attribute this mixin expects from the APIView it's combined with --
    # mypy can't otherwise see it, since IdempotentActionMixin itself doesn't inherit APIView.
    request: Request
    idempotency_service_class = IdempotencyService

    def perform_idempotent(
        self, *, scope: str, handler: Callable[[], tuple[int, object]]
    ) -> Response:
        idempotency_key = self.request.headers.get("Idempotency-Key")
        if not idempotency_key:
            response_status, body = handler()
            return Response(body, status=response_status)

        service = self.idempotency_service_class()
        try:
            result = service.run_once(
                key=idempotency_key,
                scope=scope,
                user_id=self.request.user.id,
                request_payload=self.request.data,
                handler=handler,
            )
        except IdempotencyKeyOwnershipError as exc:
            # Fixed, generic message -- never the raw exception text (CodeQL: "information
            # exposure through an exception").
            raise exceptions.PermissionDenied(
                "This Idempotency-Key cannot be used by this account."
            ) from exc
        except IdempotencyConflictError as exc:
            raise IdempotencyConflict() from exc

        return Response(result.body, status=result.status)
