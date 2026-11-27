import jwt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.request import Request

from apps.identity.repositories.user_repository import UserRepository
from apps.identity.services.token_service import TokenService

ACCESS_COOKIE_NAME = "access_token"


class JWTCookieOrHeaderAuthentication(BaseAuthentication):
    """Resolves `request.user` from the access token for every protected endpoint built from
    Issue #175 onward (TwoStepPermission -- see shared/permissions/base.py -- has nothing to
    check without this). Browser clients present the token via the `access_token` httpOnly
    cookie (ADR 0006); non-browser clients via `Authorization: Bearer <token>`. Returns
    `request.auth` as the decoded claims dict -- informational only (roles/org_id/branch_id
    may be stale per Issue #175's documented refresh-time snapshot limitation); every real
    authorization decision re-derives role assignments from the database, never from these
    claims."""

    def __init__(self) -> None:
        self._token_service = TokenService()
        self._user_repository = UserRepository()

    def authenticate(self, request: Request) -> tuple[object, dict] | None:
        raw_token = self._extract_token(request)
        if raw_token is None:
            return None

        try:
            claims = self._token_service.verify_access_token(raw_token)
        except jwt.InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed("Invalid or expired access token.") from exc

        user = self._user_repository.get_by_id(int(claims["sub"]))
        if user is None:
            raise exceptions.AuthenticationFailed("Invalid or expired access token.")

        return user, claims

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"

    @staticmethod
    def _extract_token(request: Request) -> str | None:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return header[len("Bearer ") :]
        return request.COOKIES.get(ACCESS_COOKIE_NAME)
