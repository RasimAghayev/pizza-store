from rest_framework.throttling import ScopedRateThrottle


class OtpRequestRateThrottle(ScopedRateThrottle):
    """Per-account OTP-request throttle (Issue #177, ADR 0006), shared across the email and
    phone verification channels -- ScopedRateThrottle keys by request.user on these
    IsAuthenticated-only endpoints, which is exactly per-account here. Lives in `shared/`
    rather than `apps/identity/api/throttling.py` because the endpoints that use it
    (apps/customers/api/views.py) must not import identity's view layer directly (ADR
    0004) -- unlike apps.identity.api.throttling's own classes, which only ever back
    identity's own endpoints."""

    scope = "otp_request"


class OtpConfirmRateThrottle(ScopedRateThrottle):
    """Per-account OTP-confirm-attempt throttle (Issue #177, ADR 0006) -- blunts
    brute-forcing a 6-digit code; shared across the email and phone verification channels,
    same rationale as OtpRequestRateThrottle above."""

    scope = "otp_confirm"
