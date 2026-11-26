from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck


def enforce_csrf(request) -> None:
    """Validates X-CSRFToken against the csrftoken cookie for cookie-authenticated,
    state-changing requests (ADR 0006). rest_framework.views.APIView.as_view wraps every
    view in Django's own csrf_exempt, so CsrfViewMiddleware never enforces this on its own
    -- any view that accepts cookie-based auth must call this explicitly. Reuses DRF's own
    SessionAuthentication.enforce_csrf pattern (rest_framework/authentication.py)."""
    check = CSRFCheck(lambda request: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise exceptions.PermissionDenied(f"CSRF check failed: {reason}")
