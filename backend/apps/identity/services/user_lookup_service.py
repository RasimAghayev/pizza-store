from apps.identity.models import User
from apps.identity.repositories.user_repository import UserRepository


class UserNotFoundError(Exception):
    """Raised when no identity.User row exists for the given id."""


class UserLookupService:
    """Minimal cross-module read entry point (ADR 0004) -- lets another module resolve a
    user_id to its identity.User row without importing apps.identity.models/repositories
    directly. Called by apps.customers.services.verification_service.VerificationService
    (Issue #177) to find the email address an OTP should be sent to, and to obtain the User
    instance RoleAssignmentService.assign() requires."""

    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self._user_repository = user_repository or UserRepository()

    def get_by_id(self, user_id: int) -> User:
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user
