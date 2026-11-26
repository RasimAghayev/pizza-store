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
