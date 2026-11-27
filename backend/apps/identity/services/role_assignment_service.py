from apps.identity.domain.rbac import RoleCode, is_branch_scoped, is_organization_scoped
from apps.identity.models import RoleAssignment, User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository


class InvalidRoleScopeError(Exception):
    """Raised when a role is assigned with a scope that contradicts ADR 0006's rules (e.g. a
    branch_id on an organization-scoped role, or any scope on a customer-facing role)."""


class RoleAssignmentService:
    """Explicit cross-module entry point for assigning a role to a user (ADR 0004) -- e.g.
    called by apps.customers.services.registration_service.RegistrationService.register() to
    assign the `customer` role on sign-up (Issue #176), and by
    apps.customers.services.verification_service.VerificationService to upgrade a verified
    customer to `verified_customer` (Issue #177)."""

    def __init__(self, repository: RoleAssignmentRepository | None = None) -> None:
        self._repository = repository or RoleAssignmentRepository()

    def assign(
        self,
        *,
        user: User,
        role_code: RoleCode,
        organization_id: int | None = None,
        branch_id: int | None = None,
    ) -> RoleAssignment:
        if is_branch_scoped(role_code) and branch_id is None:
            raise InvalidRoleScopeError(f"{role_code} requires a branch_id.")
        if is_organization_scoped(role_code) and organization_id is None:
            raise InvalidRoleScopeError(f"{role_code} requires an organization_id.")
        if not is_branch_scoped(role_code) and not is_organization_scoped(role_code):
            if organization_id is not None or branch_id is not None:
                raise InvalidRoleScopeError(f"{role_code} must not carry a scope.")

        return self._repository.create(
            user=user,
            role_code=role_code,
            organization_id=organization_id,
            branch_id=branch_id,
        )

    def roles_for(self, user_id: int) -> list[RoleAssignment]:
        return self._repository.for_user(user_id)
