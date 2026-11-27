from typing import cast

import factory

from apps.menu.models import MenuCategory, MenuItem
from apps.restaurants.models import Organization
from apps.restaurants.tests.factories import OrganizationFactory


class MenuCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuCategory

    # Plain field, not a SubFactory -- MenuCategory.organization_id carries no cross-app FK
    # (ADR 0004; same reasoning as Product.organization_id, see models/menu_category.py).
    # `cast` -- factory_boy's DjangoModelFactory has no installed type stubs, so mypy infers
    # OrganizationFactory()'s return type as the factory class itself, not Organization.
    organization_id = factory.LazyFunction(lambda: cast(Organization, OrganizationFactory()).id)
    name = factory.Sequence(lambda n: f"Category {n}")
    display_order = 0


class MenuItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MenuItem

    # String-form SubFactory (factory_boy's own lazy-import mechanism) -- avoids importing
    # apps.branches/apps.products directly in this module, same reasoning as MenuItem's own
    # lazy string FKs (ADR 0004; see models/menu_item.py). Each SubFactory spins up its own
    # independent Organization by default -- callers that need a branch/product/category
    # under the *same* organization (e.g. to exercise MenuService.create_item's real
    # validation) pass explicit instances instead of relying on these defaults.
    branch = factory.SubFactory("apps.branches.tests.factories.BranchFactory")
    product = factory.SubFactory("apps.products.tests.factories.ProductFactory")
    category = factory.SubFactory(MenuCategoryFactory)
    is_available = True
    available_from = None
    available_until = None
    display_order = 0
