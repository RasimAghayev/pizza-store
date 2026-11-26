from dataclasses import dataclass

from apps.identity.models import User
from apps.identity.services.authentication_service import AuthenticationService
from apps.identity.services.token_service import TokenService


class InvalidCredentialsError(Exception):
    """Raised when login is attempted with an unknown email or wrong password."""


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    user: User


class SessionService:
    """One entry point per auth use case (ADR 0004) -- orchestrates AuthenticationService
    (credential verification) and TokenService (JWT/refresh-token mechanics) for the three
    endpoints in apps/identity/api/views.py."""

    def __init__(
        self,
        authentication_service: AuthenticationService | None = None,
        token_service: TokenService | None = None,
    ) -> None:
        self._authentication_service = authentication_service or AuthenticationService()
        self._token_service = token_service or TokenService()

    def login(
        self, *, email: str, password: str, device_label: str = "", ip_address: str | None = None
    ) -> TokenPair:
        user = self._authentication_service.verify_credentials(email, password)
        if user is None:
            raise InvalidCredentialsError("Invalid email or password.")

        access_token = self._token_service.issue_access_token(user)
        refresh_token, _ = self._token_service.issue_refresh_token(
            user, device_label=device_label, ip_address=ip_address
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token, user=user)

    def refresh(
        self, *, raw_refresh_token: str, device_label: str = "", ip_address: str | None = None
    ) -> TokenPair:
        access_token, new_refresh_token, record = self._token_service.rotate_refresh_token(
            raw_refresh_token, device_label=device_label, ip_address=ip_address
        )
        return TokenPair(
            access_token=access_token, refresh_token=new_refresh_token, user=record.user
        )

    def logout(self, *, raw_refresh_token: str) -> None:
        self._token_service.revoke_family_for_token(raw_refresh_token)
