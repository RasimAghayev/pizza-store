from apps.products.models import OptionChoice, OptionGroup, Product, ProductTopping
from apps.products.repositories.allergen_repository import AllergenRepository
from apps.products.repositories.option_choice_repository import OptionChoiceRepository
from apps.products.repositories.option_group_repository import OptionGroupRepository
from apps.products.repositories.product_repository import ProductRepository
from apps.products.repositories.product_topping_repository import ProductToppingRepository
from apps.products.repositories.topping_repository import ToppingRepository
from apps.products.services.catalog_service import AllergenNotFoundError, ToppingNotFoundError

# calls apps.restaurants.services.organization_service.OrganizationService.get_by_id() --
# see backend/apps/restaurants/README.md. products never imports apps.restaurants.models/
# repositories directly (ADR 0004); Product.organization_id is a plain field for the same
# reason (same no-cross-app-FK pattern as apps.identity.RoleAssignment, see model docstring).
from apps.restaurants.services.organization_service import (
    OrganizationNotFoundError,
    OrganizationService,
)


class ProductNotFoundError(Exception):
    pass


class OptionGroupNotFoundError(Exception):
    pass


class OptionChoiceNotFoundError(Exception):
    pass


class ProductService:
    def __init__(
        self,
        repository: ProductRepository | None = None,
        option_group_repository: OptionGroupRepository | None = None,
        option_choice_repository: OptionChoiceRepository | None = None,
        topping_repository: ToppingRepository | None = None,
        product_topping_repository: ProductToppingRepository | None = None,
        allergen_repository: AllergenRepository | None = None,
        organization_service: OrganizationService | None = None,
    ) -> None:
        self._repository = repository or ProductRepository()
        self._option_groups = option_group_repository or OptionGroupRepository()
        self._option_choices = option_choice_repository or OptionChoiceRepository()
        self._toppings = topping_repository or ToppingRepository()
        self._product_toppings = product_topping_repository or ProductToppingRepository()
        self._allergens = allergen_repository or AllergenRepository()
        self._organization_service = organization_service or OrganizationService()

    def create(
        self,
        *,
        organization_id: int,
        name: str,
        description: str = "",
        base_price,
        is_active: bool = True,
        allergen_ids=None,
    ) -> Product:
        if self._organization_service.get_by_id(organization_id) is None:
            raise OrganizationNotFoundError(organization_id)
        product = self._repository.create(
            organization_id=organization_id,
            name=name,
            description=description,
            base_price=base_price,
            is_active=is_active,
        )
        if allergen_ids:
            self._assert_allergen_ids_exist(allergen_ids)
            self._allergens.set_for_product(product, allergen_ids)
        return product

    def get_by_id(self, product_id: int) -> Product | None:
        return self._repository.get_by_id(product_id)

    def list_for_organization(self, organization_id: int) -> list[Product]:
        return self._repository.all_for_organization(organization_id)

    def update(self, product_id: int, *, allergen_ids=None, **fields) -> Product:
        product = self._repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if fields:
            self._repository.update(product, **fields)
        if allergen_ids is not None:
            self._assert_allergen_ids_exist(allergen_ids)
            self._allergens.set_for_product(product, allergen_ids)
        return product

    def delete(self, product_id: int) -> None:
        product = self._repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        self._repository.delete(product)

    def add_option_group(
        self, *, product_id: int, kind: str, is_required: bool = True, allows_multiple: bool = False
    ) -> OptionGroup:
        if self._repository.get_by_id(product_id) is None:
            raise ProductNotFoundError(product_id)
        return self._option_groups.create(
            product_id=product_id,
            kind=kind,
            is_required=is_required,
            allows_multiple=allows_multiple,
        )

    def option_groups_for(self, product_id: int) -> list[OptionGroup]:
        return self._option_groups.all_for_product(product_id)

    def get_option_group(self, option_group_id: int) -> OptionGroup | None:
        return self._option_groups.get_by_id(option_group_id)

    def add_option_choice(self, *, option_group_id: int, name: str, price_delta) -> OptionChoice:
        if self._option_groups.get_by_id(option_group_id) is None:
            raise OptionGroupNotFoundError(option_group_id)
        return self._option_choices.create(
            option_group_id=option_group_id, name=name, price_delta=price_delta
        )

    def option_choices_for(self, option_group_id: int) -> list[OptionChoice]:
        return self._option_choices.all_for_option_group(option_group_id)

    def attach_topping(
        self, *, product_id: int, topping_id: int, is_default_included: bool = False
    ) -> ProductTopping:
        if self._repository.get_by_id(product_id) is None:
            raise ProductNotFoundError(product_id)
        if self._toppings.get_by_id(topping_id) is None:
            raise ToppingNotFoundError(topping_id)
        return self._product_toppings.attach(
            product_id=product_id, topping_id=topping_id, is_default_included=is_default_included
        )

    def toppings_for(self, product_id: int) -> list[ProductTopping]:
        return self._product_toppings.all_for_product(product_id)

    def detach_topping(self, *, product_id: int, topping_id: int) -> None:
        product_topping = self._product_toppings.get(product_id=product_id, topping_id=topping_id)
        if product_topping is None:
            raise ToppingNotFoundError(topping_id)
        self._product_toppings.detach(product_topping)

    def allergens_for(self, product_id: int):
        product = self._repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return self._allergens.for_product_union_default_toppings(product)

    def _assert_allergen_ids_exist(self, allergen_ids) -> None:
        found_ids = {a.pk for a in self._allergens.filter_by_ids(allergen_ids)}
        missing = set(allergen_ids) - found_ids
        if missing:
            raise AllergenNotFoundError(sorted(missing))
