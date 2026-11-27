from apps.restaurants.models import Organization
from apps.restaurants.repositories.organization_repository import OrganizationRepository


class OrganizationNotFoundError(Exception):
    pass


class OrganizationService:
    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self._repository = repository or OrganizationRepository()

    def create(self, *, name: str, owner_user_id: int) -> Organization:
        return self._repository.create(name=name, owner_user_id=owner_user_id)

    def get_by_id(self, organization_id: int) -> Organization | None:
        return self._repository.get_by_id(organization_id)

    def update(self, organization_id: int, **fields: object) -> Organization:
        organization = self._repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError(organization_id)
        return self._repository.update(organization, **fields)

    def delete(self, organization_id: int) -> None:
        organization = self._repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError(organization_id)
        self._repository.delete(organization)

    def list_visible_to(self, user: object) -> list[Organization]:
        """Organization is staff-only (unlike Restaurant/Branch, it has no public read path)
        -- step 1 of TwoStepPermission already proved the caller holds `restaurants.view`
        *somewhere*; this re-derives *which* organizations that actually covers rather than
        returning every row to anyone who passes step 1, since `list`/`create` never reach
        `TwoStepPermission.has_object_permission` (ADR 0006: scope is always re-derived from
        the resource, never assumed). An unscoped grant (e.g. Super Admin) sees every
        organization; an org-scoped grant sees only its own; a purely branch-scoped grant
        (e.g. Branch Manager) sees none -- organization browsing isn't their job."""
        assignments = user.role_assignments_granting("restaurants.view")  # type: ignore[attr-defined]
        if any(a.organization_id is None and a.branch_id is None for a in assignments):
            return self._repository.all()
        organization_ids = {a.organization_id for a in assignments if a.organization_id is not None}
        if not organization_ids:
            return []
        return self._repository.filter_by_ids(organization_ids)
