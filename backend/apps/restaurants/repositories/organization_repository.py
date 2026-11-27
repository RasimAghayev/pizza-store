from apps.restaurants.models import Organization


class OrganizationRepository:
    """Only file in this module allowed to issue an ORM query for Organization, per ADR 0004."""

    def create(self, *, name: str, owner_user_id: int) -> Organization:
        return Organization.objects.create(name=name, owner_user_id=owner_user_id)

    def get_by_id(self, organization_id: int) -> Organization | None:
        return Organization.objects.filter(pk=organization_id).first()

    def all(self) -> list[Organization]:
        return list(Organization.objects.order_by("name"))

    def filter_by_ids(self, organization_ids: set[int]) -> list[Organization]:
        return list(Organization.objects.filter(pk__in=organization_ids).order_by("name"))

    def update(self, organization: Organization, **fields: object) -> Organization:
        for field, value in fields.items():
            setattr(organization, field, value)
        organization.save(update_fields=list(fields))
        return organization

    def delete(self, organization: Organization) -> None:
        organization.delete()
