import hashlib
import secrets

from django.core.cache import cache

from apps.identity.repositories.user_repository import UserRepository
from apps.identity.services.token_service import TokenService
from shared.notifications.console_gateway import send_console_email

# No suggested rate exists in the Issue for this specific value -- chosen to match the
# 5-minute OTP TTL's order of magnitude while giving a real user enough time to open their
# inbox and follow the link, consistent with common password-reset-token lifetimes.
RESET_TOKEN_TTL_SECONDS = 30 * 60


class InvalidResetTokenError(Exception):
    """Raised for a missing, expired, or already-used reset token."""


def _reset_cache_key(token_hash: str) -> str:
    return f"pwreset:{token_hash}"


def _generate_raw_token() -> str:
    """A separate, patchable seam -- `secrets` is a shared module object, so monkeypatching
    `secrets.token_urlsafe` itself in a test would also change
    apps.identity.services.token_service.TokenService's unrelated refresh-token generation."""
    return secrets.token_urlsafe(32)


class PasswordRecoveryService:
    """Password reset (Issue #177) -- lives in identity, not customers: resetting a
    credential is identity's own domain, no customer-profile concept needed. Sends via
    shared/notifications/console_gateway.py directly, never through
    apps.customers.services.notification_gateway.NotificationGateway, to avoid a backwards
    identity -> customers cross-module call (ADR 0004 establishes customers depends on
    identity, never the reverse -- see apps/customers/services/registration_service.py)."""

    def __init__(
        self,
        *,
        user_repository: UserRepository | None = None,
        token_service: TokenService | None = None,
    ) -> None:
        self._user_repository = user_repository or UserRepository()
        self._token_service = token_service or TokenService()

    def request_reset(self, email: str) -> None:
        user = self._user_repository.get_by_email(email)
        if user is None:
            # Deliberately a silent no-op, not a NotFound-style error: revealing whether an
            # email is registered is an account-enumeration vector. The view returns the same
            # generic 200 response regardless of whether this branch ran.
            return

        raw_token = _generate_raw_token()
        cache.set(_reset_cache_key(self._hash(raw_token)), user.pk, timeout=RESET_TOKEN_TTL_SECONDS)
        send_console_email(
            to_email=user.email,
            subject="Reset your Pizza Store password",
            body=f"Use this token to reset your password: {raw_token}. It expires in 30 minutes.",
        )

    def confirm_reset(self, *, token: str, new_password: str) -> None:
        key = _reset_cache_key(self._hash(token))
        user_id = cache.get(key)
        if user_id is None:
            raise InvalidResetTokenError("Invalid or expired reset token.")
        cache.delete(key)

        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise InvalidResetTokenError("Invalid or expired reset token.")

        self._user_repository.set_password(user, new_password)
        # Stolen-token-style response (ADR 0006): a password reset must kill every existing
        # session, not just the one tied to whichever refresh token happens to be presented
        # next.
        self._token_service.revoke_all_for_user(user_id)

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()
