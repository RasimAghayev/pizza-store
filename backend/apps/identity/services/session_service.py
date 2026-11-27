from dataclasses import dataclass

from apps.identity.models import RoleAssignment, User
from apps.identity.services.authentication_service import AuthenticationService
from apps.identity.services.role_assignment_service import RoleAssignmentService
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
        role_assignment_service: RoleAssignmentService | None = None,
    ) -> None:
        self._authentication_service = authentication_service or AuthenticationService()
        self._token_service = token_service or TokenService()
        self._role_assignment_service = role_assignment_service or RoleAssignmentService()

    def login(
        self, *, email: str, password: str, device_label: str = "", ip_address: str | None = None
    ) -> TokenPair:
        user = self._authentication_service.verify_credentials(email, password)
        if user is None:
            raise InvalidCredentialsError("Invalid email or password.")

        roles, org_id, branch_id = self._claims_for(user)
        access_token = self._token_service.issue_access_token(
            user, roles=roles, org_id=org_id, branch_id=branch_id
        )
        refresh_token, _ = self._token_service.issue_refresh_token(
            user,
            roles=roles,
            org_id=org_id,
            branch_id=branch_id,
            device_label=device_label,
            ip_address=ip_address,
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token, user=user)

    def _claims_for(self, user: User) -> tuple[list[str], int | None, int | None]:
        assignments: list[RoleAssignment] = self._role_assignment_service.roles_for(user.pk)
        roles = [assignment.role_code for assignment in assignments]

        scoped = [
            a for a in assignments if a.organization_id is not None or a.branch_id is not None
        ]
        if len(scoped) == 1:
            return roles, scoped[0].organization_id, scoped[0].branch_id
        # Zero or multiple scoped assignments: the JWT claim stays null (informational/
        # logging-only, per ADR 0006's `jti` precedent) -- every real permission check
        # re-derives scope per-assignment at request time regardless (Issue #175).
        return roles, None, None

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
