from apps.identity.domain.rbac import RoleCode
from apps.identity.models import RoleAssignment, User


class RoleAssignmentRepository:
    """Only file in this module allowed to issue an ORM query for RoleAssignment, per ADR 0004."""

    def create(
        self,
        *,
        user: User,
        role_code: RoleCode,
        organization_id: int | None = None,
        branch_id: int | None = None,
    ) -> RoleAssignment:
        return RoleAssignment.objects.create(
            user=user,
            role_code=role_code,
            organization_id=organization_id,
            branch_id=branch_id,
        )

    def for_user(self, user_id: int) -> list[RoleAssignment]:
        return list(RoleAssignment.objects.filter(user_id=user_id))

    def has_role(self, *, user_id: int, role_code: RoleCode) -> bool:
        return RoleAssignment.objects.filter(user_id=user_id, role_code=role_code).exists()
