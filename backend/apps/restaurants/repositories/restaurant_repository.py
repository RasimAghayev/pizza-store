from apps.restaurants.models import Organization, Restaurant


class RestaurantRepository:
    """Only file in this module allowed to issue an ORM query for Restaurant, per ADR 0004."""

    def create(self, *, organization: Organization, name: str, description: str = "") -> Restaurant:
        return Restaurant.objects.create(
            organization=organization, name=name, description=description
        )

    def get_by_id(self, restaurant_id: int) -> Restaurant | None:
        return Restaurant.objects.filter(pk=restaurant_id).select_related("organization").first()

    def all(self) -> list[Restaurant]:
        return list(Restaurant.objects.select_related("organization").order_by("name"))

    def update(self, restaurant: Restaurant, **fields: object) -> Restaurant:
        for field, value in fields.items():
            setattr(restaurant, field, value)
        restaurant.save(update_fields=list(fields))
        return restaurant

    def delete(self, restaurant: Restaurant) -> None:
        restaurant.delete()
