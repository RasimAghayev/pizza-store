from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    """Per-IP throttle (ADR 0006) -- ScopedRateThrottle keys by request.user when
    authenticated, else by client IP, which is exactly per-IP here since login requests are
    always anonymous."""

    scope = "login"


class LoginAccountRateThrottle(SimpleRateThrottle):
    """Per-account login throttle (ADR 0006), independent of LoginRateThrottle's per-IP key
    -- caps credential stuffing against one account even when spread across many source
    IPs. Keyed by the submitted email, not request.user, since the request is anonymous."""

    scope = "login_account"

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class RefreshRateThrottle(ScopedRateThrottle):
    scope = "refresh"


class PasswordResetRequestRateThrottle(SimpleRateThrottle):
    """Per-submitted-email throttle (Issue #177), same pattern as LoginAccountRateThrottle
    above -- the request is always anonymous, so there is no request.user to key on."""

    scope = "password_reset_request"

    def get_cache_key(self, request, view):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class PasswordResetConfirmRateThrottle(ScopedRateThrottle):
    """Per-IP throttle (Issue #177) -- a reset-confirm request carries only an opaque token,
    no account identifier to key on until the token itself is validated, same per-IP
    rationale as LoginRateThrottle above."""

    scope = "password_reset_confirm"
