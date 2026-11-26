import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

logger = logging.getLogger(__name__)

_STATUS_CODE_TO_ERROR_CODE = {
    400: "validation_error",
    401: "authentication_failed",
    403: "permission_denied",
    404: "not_found",
}

_DEFAULT_MESSAGE = {
    "validation_error": "Validation failed.",
    "authentication_failed": "Authentication failed.",
    "permission_denied": "You do not have permission to perform this action.",
    "not_found": "Not found.",
    "internal_error": "An unexpected error occurred.",
}


def _error_code_for(status_code: int) -> str:
    if status_code in _STATUS_CODE_TO_ERROR_CODE:
        return _STATUS_CODE_TO_ERROR_CODE[status_code]
    return "internal_error" if status_code >= 500 else "validation_error"


def api_exception_handler(exc, context):
    """Registered as REST_FRAMEWORK['EXCEPTION_HANDLER'] in config/settings.py so every
    DRF view, in every module, raises the same {"error": {code, message, details}} envelope
    -- see docs/api/conventions.md for the shape and code taxonomy."""
    response = drf_default_exception_handler(exc, context)

    if response is None:
        # Not a recognized DRF APIException/Http404/PermissionDenied: an unexpected server
        # error. Log the real exception server-side; never let its message or traceback
        # reach the client, including when DEBUG=False.
        logger.exception("Unhandled exception in API view", exc_info=exc)
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": _DEFAULT_MESSAGE["internal_error"],
                    "details": {},
                }
            },
            status=500,
        )

    code = _error_code_for(response.status_code)
    data = response.data

    if isinstance(data, dict) and set(data) == {"detail"}:
        message = str(data["detail"])
        details: dict = {}
    else:
        message = _DEFAULT_MESSAGE[code]
        details = data if isinstance(data, dict) else {"non_field_errors": data}

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
