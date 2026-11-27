from django.middleware.csrf import get_token
from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.api.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
)
from apps.identity.api.throttling import (
    LoginAccountRateThrottle,
    LoginRateThrottle,
    PasswordResetConfirmRateThrottle,
    PasswordResetRequestRateThrottle,
    RefreshRateThrottle,
)
from apps.identity.services.password_recovery_service import (
    InvalidResetTokenError,
    PasswordRecoveryService,
)
from apps.identity.services.session_service import InvalidCredentialsError, SessionService
from apps.identity.services.token_service import (
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    InvalidRefreshTokenError,
    StolenRefreshTokenError,
)
from shared.api.csrf import enforce_csrf

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

_COOKIE_KWARGS = {"httponly": True, "secure": True, "samesite": "Strict"}


def _client_type(request) -> str:
    value = request.headers.get("X-Client-Type")
    if value not in ("browser", "native"):
        raise exceptions.ValidationError(
            {"X-Client-Type": "Required header; must be 'browser' or 'native'."}
        )
    return value


def _client_ip(request) -> str | None:
    return request.META.get("REMOTE_ADDR")


def _refresh_cookie_path(version: str) -> str:
    """Scoped to the whole auth module (login/refresh/logout), not just "/refresh" --
    LogoutView also needs to read this cookie to revoke the token, and a browser only
    attaches a Path-scoped cookie to requests whose path matches that scope (ADR 0006)."""
    return f"/api/{version}/auth"


def _set_auth_cookies(
    response: Response, *, access_token: str, refresh_token: str, version: str
) -> None:
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        max_age=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        path="/",
        **_COOKIE_KWARGS,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=_refresh_cookie_path(version),
        **_COOKIE_KWARGS,
    )


def _clear_auth_cookies(response: Response, *, version: str) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path=_refresh_cookie_path(version))


def _read_refresh_token(request, *, client_type: str) -> str:
    """Browser clients present the refresh token via the httpOnly cookie (CSRF-checked,
    since this is a cookie-authenticated state-changing request -- ADR 0006); non-browser
    clients present it in the request body."""
    if client_type == "browser":
        enforce_csrf(request)
        raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not raw_token:
            raise exceptions.AuthenticationFailed("Missing refresh token cookie.")
        return raw_token

    serializer = RefreshSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    raw_token = serializer.validated_data.get("refresh_token")
    if not raw_token:
        # Field name, not a credential -- Bandit's B105 heuristic flags any dict key
        # containing "token".
        raise exceptions.ValidationError({"refresh_token": "This field is required."})  # nosec B105
    return raw_token


class _ReturnsAuthenticationFailedAs401:
    """DRF's default exception handler downgrades AuthenticationFailed to 403 when a view
    has no authenticator to supply a WWW-Authenticate header (rest_framework/views.py's
    exception_handler). These views intentionally have none -- login/refresh ARE the
    pre-auth entry points -- so override get_authenticate_header to keep the conventional
    401 for invalid credentials/invalid refresh tokens."""

    def get_authenticate_header(self, request):
        return "Bearer"


class LoginView(_ReturnsAuthenticationFailedAs401, APIView):
    """calls SessionService.login() -- see apps/identity/services/session_service.py"""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle, LoginAccountRateThrottle]

    def post(self, request, version):
        client_type = _client_type(request)
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            pair = SessionService().login(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                device_label=request.headers.get("User-Agent", "")[:255],
                ip_address=_client_ip(request),
            )
        except InvalidCredentialsError as exc:
            # Generic, exception-independent message -- never forward str(exc) into a
            # client-facing response (CodeQL py/stack-trace-exposure, CWE-209).
            raise exceptions.AuthenticationFailed("Invalid email or password.") from exc

        # Seeds the CSRF cookie needed for the subsequent cookie-authenticated
        # refresh/logout calls in browser mode -- no prior session exists yet to forge by
        # the time this request is made, so this endpoint does not itself require
        # X-CSRFToken (see docs/api/conventions.md for this explicitly scoped deviation).
        get_token(request)

        if client_type == "browser":
            response = Response({"message": "Login successful."})
            _set_auth_cookies(
                response,
                access_token=pair.access_token,
                refresh_token=pair.refresh_token,
                version=version,
            )
        else:
            response = Response(
                {"access_token": pair.access_token, "refresh_token": pair.refresh_token}
            )
        return response


class RefreshView(_ReturnsAuthenticationFailedAs401, APIView):
    """calls SessionService.refresh() -- see apps/identity/services/session_service.py"""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [RefreshRateThrottle]

    def post(self, request, version):
        client_type = _client_type(request)
        raw_token = _read_refresh_token(request, client_type=client_type)

        try:
            pair = SessionService().refresh(
                raw_refresh_token=raw_token,
                device_label=request.headers.get("User-Agent", "")[:255],
                ip_address=_client_ip(request),
            )
        except (InvalidRefreshTokenError, StolenRefreshTokenError) as exc:
            # Generic, exception-independent message -- never forward str(exc) into a
            # client-facing response (CodeQL py/stack-trace-exposure, CWE-209). Also avoids
            # telling a caller whether a token was merely expired/unknown vs. a detected
            # reuse of an already-rotated token.
            raise exceptions.AuthenticationFailed("Invalid or expired refresh token.") from exc

        if client_type == "browser":
            response = Response({"message": "Token refreshed."})
            _set_auth_cookies(
                response,
                access_token=pair.access_token,
                refresh_token=pair.refresh_token,
                version=version,
            )
        else:
            response = Response(
                {"access_token": pair.access_token, "refresh_token": pair.refresh_token}
            )
        return response


class LogoutView(APIView):
    """calls SessionService.logout() -- see apps/identity/services/session_service.py"""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request, version):
        client_type = _client_type(request)
        raw_token = _read_refresh_token(request, client_type=client_type)

        SessionService().logout(raw_refresh_token=raw_token)

        response = Response({"message": "Logged out."})
        if client_type == "browser":
            _clear_auth_cookies(response, version=version)
        return response


class PasswordResetRequestView(APIView):
    """calls PasswordRecoveryService.request_reset() -- see
    apps/identity/services/password_recovery_service.py."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestRateThrottle]

    def post(self, request, version):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PasswordRecoveryService().request_reset(serializer.validated_data["email"])
        # Always the same generic response regardless of whether the email is registered --
        # see PasswordRecoveryService.request_reset's own account-enumeration rationale.
        return Response({"message": "If that email is registered, a reset link has been sent."})


class PasswordResetConfirmView(_ReturnsAuthenticationFailedAs401, APIView):
    """calls PasswordRecoveryService.confirm_reset() -- see
    apps/identity/services/password_recovery_service.py."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetConfirmRateThrottle]

    def post(self, request, version):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            PasswordRecoveryService().confirm_reset(
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        except InvalidResetTokenError as exc:
            # Generic, exception-independent message -- never forward str(exc) into a
            # client-facing response (CodeQL py/stack-trace-exposure, CWE-209).
            raise exceptions.AuthenticationFailed("Invalid or expired reset token.") from exc
        return Response({"message": "Password has been reset."})
