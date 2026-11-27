from apps.restaurants.models import Restaurant
from apps.restaurants.repositories.organization_repository import OrganizationRepository
from apps.restaurants.repositories.restaurant_repository import RestaurantRepository
from apps.restaurants.services.organization_service import OrganizationNotFoundError


class RestaurantNotFoundError(Exception):
    pass


class RestaurantService:
    def __init__(
        self,
        repository: RestaurantRepository | None = None,
        organization_repository: OrganizationRepository | None = None,
    ) -> None:
        self._repository = repository or RestaurantRepository()
        self._organization_repository = organization_repository or OrganizationRepository()

    def create(self, *, organization_id: int, name: str, description: str = "") -> Restaurant:
        organization = self._organization_repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundError(organization_id)
        return self._repository.create(
            organization=organization, name=name, description=description
        )

    def get_by_id(self, restaurant_id: int) -> Restaurant | None:
        return self._repository.get_by_id(restaurant_id)

    def list_all(self) -> list[Restaurant]:
        """Unfiltered -- the public, AllowAny read path (menu-browsing needs this before
        login exists, Issue #180's Implementation Prompt). Every restaurant is visible to
        every caller; there is no staff-only variant of this method."""
        return self._repository.all()

    def update(self, restaurant_id: int, **fields: object) -> Restaurant:
        restaurant = self._repository.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundError(restaurant_id)
        return self._repository.update(restaurant, **fields)

    def delete(self, restaurant_id: int) -> None:
        restaurant = self._repository.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundError(restaurant_id)
        self._repository.delete(restaurant)
