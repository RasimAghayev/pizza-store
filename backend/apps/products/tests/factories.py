from decimal import Decimal
from typing import cast

import factory

from apps.products.models import (
    Allergen,
    OptionChoice,
    OptionGroup,
    OptionGroupKind,
    Product,
    Topping,
)
from apps.restaurants.models import Organization
from apps.restaurants.tests.factories import OrganizationFactory


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    # Plain field, not a SubFactory -- Product.organization_id carries no cross-app FK
    # (ADR 0004; see models/product.py), same reasoning as RoleAssignment's organization_id.
    # A real Organization row is still created so ProductService.create()'s existence check
    # (via OrganizationService) passes by default in tests that don't care about that path.
    # `cast` -- factory_boy's DjangoModelFactory has no installed type stubs, so mypy infers
    # OrganizationFactory()'s return type as the factory class itself, not Organization.
    organization_id = factory.LazyFunction(lambda: cast(Organization, OrganizationFactory()).id)
    name = factory.Sequence(lambda n: f"Pizza {n}")
    description = ""
    base_price = Decimal("10.00")
    is_active = True


class OptionGroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OptionGroup

    product = factory.SubFactory(ProductFactory)
    kind = OptionGroupKind.SIZE
    is_required = True
    allows_multiple = False


class OptionChoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OptionChoice

    option_group = factory.SubFactory(OptionGroupFactory)
    name = factory.Sequence(lambda n: f"Choice {n}")
    price_delta = Decimal("0.00")


class ToppingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Topping

    name = factory.Sequence(lambda n: f"Topping {n}")
    price_delta = Decimal("1.00")
    sku_reference = None


class AllergenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Allergen

    name = factory.Sequence(lambda n: f"Allergen {n}")
