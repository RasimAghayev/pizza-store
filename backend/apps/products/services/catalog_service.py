from apps.products.models import Allergen, Topping
from apps.products.repositories.allergen_repository import AllergenRepository
from apps.products.repositories.topping_repository import ToppingRepository


class ToppingNotFoundError(Exception):
    pass


class AllergenNotFoundError(Exception):
    pass


class CatalogService:
    """Platform-wide Topping/Allergen catalog -- shared across every organization, so
    management is unscoped-only (see api/views.py's `_PlatformCatalogScoped` mixin);
    an org can attach *existing* catalog toppings to its own products via `ProductService`,
    a separate, product-scoped permission check."""

    def __init__(
        self,
        topping_repository: ToppingRepository | None = None,
        allergen_repository: AllergenRepository | None = None,
    ) -> None:
        self._toppings = topping_repository or ToppingRepository()
        self._allergens = allergen_repository or AllergenRepository()

    def create_topping(
        self, *, name: str, price_delta, sku_reference: str | None = None, allergen_ids=None
    ) -> Topping:
        topping = self._toppings.create(
            name=name, price_delta=price_delta, sku_reference=sku_reference
        )
        if allergen_ids:
            self._assert_allergen_ids_exist(allergen_ids)
            self._allergens.set_for_topping(topping, allergen_ids)
        return topping

    def get_topping(self, topping_id: int) -> Topping | None:
        return self._toppings.get_by_id(topping_id)

    def list_toppings(self) -> list[Topping]:
        return self._toppings.all()

    def update_topping(self, topping_id: int, *, allergen_ids=None, **fields) -> Topping:
        topping = self._toppings.get_by_id(topping_id)
        if topping is None:
            raise ToppingNotFoundError(topping_id)
        if fields:
            self._toppings.update(topping, **fields)
        if allergen_ids is not None:
            self._assert_allergen_ids_exist(allergen_ids)
            self._allergens.set_for_topping(topping, allergen_ids)
        return topping

    def delete_topping(self, topping_id: int) -> None:
        topping = self._toppings.get_by_id(topping_id)
        if topping is None:
            raise ToppingNotFoundError(topping_id)
        self._toppings.delete(topping)

    def create_allergen(self, *, name: str) -> Allergen:
        return self._allergens.create(name=name)

    def get_allergen(self, allergen_id: int) -> Allergen | None:
        return self._allergens.get_by_id(allergen_id)

    def list_allergens(self) -> list[Allergen]:
        return self._allergens.all()

    def delete_allergen(self, allergen_id: int) -> None:
        allergen = self._allergens.get_by_id(allergen_id)
        if allergen is None:
            raise AllergenNotFoundError(allergen_id)
        allergen.delete()

    def _assert_allergen_ids_exist(self, allergen_ids) -> None:
        found_ids = {a.pk for a in self._allergens.filter_by_ids(allergen_ids)}
        missing = set(allergen_ids) - found_ids
        if missing:
            raise AllergenNotFoundError(sorted(missing))
