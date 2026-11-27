import datetime as dt
import hashlib
import secrets
import uuid
from collections.abc import Sequence

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.utils import timezone

from apps.identity.models import RefreshToken, User
from apps.identity.repositories.refresh_token_repository import RefreshTokenRepository

ACCESS_TOKEN_LIFETIME = dt.timedelta(minutes=15)
REFRESH_TOKEN_LIFETIME = dt.timedelta(days=14)
JWT_ALGORITHM = "RS256"
_KEY_ID = "local-default"


def _load_or_generate_private_key():
    pem = settings.JWT_PRIVATE_KEY_PEM
    if pem:
        try:
            return serialization.load_pem_private_key(pem.encode(), password=None)
        except ValueError:
            # The mounted secret isn't a real PEM key -- e.g. the tracked
            # jwt_private_key.txt.example placeholder, copied in by CI workflows that don't
            # run scripts/generate-jwt-keypair.py (see docs/security/secret-management.md).
            # Deliberately not a real-looking PEM block: Gitleaks'/GitGuardian's private-key
            # detectors flag any valid PEM structure regardless of it being a throwaway key.
            pass
    # No usable `jwt_private_key` Compose secret (absent, or the placeholder above) --
    # generate a process-local keypair so sign/verify still round-trips within this process.
    # Never persisted; a restart invalidates every token issued under it, which is fine for a
    # throwaway/test process.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


_PRIVATE_KEY = _load_or_generate_private_key()
_PUBLIC_KEY = _PRIVATE_KEY.public_key()


class InvalidRefreshTokenError(Exception):
    """Raised for a refresh token that is missing, unknown, or expired."""


class StolenRefreshTokenError(Exception):
    """Raised when an already-rotated refresh token is presented again (ADR 0006) -- the
    entire token family has just been revoked as a side effect of raising this."""


class TokenService:
    def __init__(self, refresh_token_repository: RefreshTokenRepository | None = None) -> None:
        self._refresh_token_repository = refresh_token_repository or RefreshTokenRepository()

    def issue_access_token(
        self,
        user: User,
        *,
        roles: Sequence[str] = (),
        org_id: int | None = None,
        branch_id: int | None = None,
    ) -> str:
        now = dt.datetime.now(dt.timezone.utc)
        payload: dict[str, object] = {
            "sub": str(user.pk),
            "roles": list(roles),
            "org_id": org_id,
            "branch_id": branch_id,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + ACCESS_TOKEN_LIFETIME,
        }
        return jwt.encode(payload, _PRIVATE_KEY, algorithm=JWT_ALGORITHM, headers={"kid": _KEY_ID})

    def verify_access_token(self, token: str) -> dict:
        return jwt.decode(token, _PUBLIC_KEY, algorithms=[JWT_ALGORITHM])

    def issue_refresh_token(
        self,
        user: User,
        *,
        roles: Sequence[str] = (),
        org_id: int | None = None,
        branch_id: int | None = None,
        device_label: str = "",
        ip_address: str | None = None,
    ) -> tuple[str, RefreshToken]:
        raw_token = secrets.token_urlsafe(48)
        now = timezone.now()
        record = self._refresh_token_repository.create(
            user=user,
            token_hash=self._hash(raw_token),
            issued_at=now,
            expires_at=now + REFRESH_TOKEN_LIFETIME,
            device_label=device_label,
            ip_address=ip_address,
            roles_snapshot=list(roles),
            organization_id=org_id,
            branch_id=branch_id,
        )
        return raw_token, record

    def rotate_refresh_token(
        self, raw_token: str, *, device_label: str = "", ip_address: str | None = None
    ) -> tuple[str, str, RefreshToken]:
        record = self._refresh_token_repository.get_by_hash(self._hash(raw_token))
        if record is None:
            raise InvalidRefreshTokenError("Unknown refresh token.")
        if record.revoked_at is not None:
            self._refresh_token_repository.revoke_family(record)
            raise StolenRefreshTokenError("Refresh token reuse detected; family revoked.")
        if record.expires_at <= timezone.now():
            raise InvalidRefreshTokenError("Refresh token has expired.")

        self._refresh_token_repository.revoke(record)
        # Carries the original login's roles/org_id/branch_id forward unchanged (ADR 0006 --
        # see Issue #175) rather than re-querying role_assignments on every refresh; a role
        # change takes effect on the account's next full login, a documented limitation.
        new_raw_token, new_record = self.issue_refresh_token(
            record.user,
            roles=record.roles_snapshot,
            org_id=record.organization_id,
            branch_id=record.branch_id,
            device_label=device_label,
            ip_address=ip_address,
        )
        self._refresh_token_repository.mark_replaced(record, new_record)
        access_token = self.issue_access_token(
            record.user,
            roles=record.roles_snapshot,
            org_id=record.organization_id,
            branch_id=record.branch_id,
        )
        return access_token, new_raw_token, new_record

    def revoke_family_for_token(self, raw_token: str) -> None:
        record = self._refresh_token_repository.get_by_hash(self._hash(raw_token))
        if record is not None:
            self._refresh_token_repository.revoke_family(record)

    def revoke_all_for_user(self, user_id: int) -> None:
        """calls apps.identity.services.password_recovery_service.PasswordRecoveryService
        .confirm_reset() -- a password reset revokes every existing session, not just one
        token family (Issue #177, ADR 0006)."""
        self._refresh_token_repository.revoke_all_for_user(user_id)

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()
