from decimal import Decimal
from typing import cast

import factory

from apps.cart.models import Cart, CartItem
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory


class CartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cart

    # Plain field, not a SubFactory -- Cart.customer_id carries no cross-app FK (ADR 0004;
    # see models/cart.py), same reasoning as Product.organization_id. A real Customer row is
    # still created so CartService.get_or_create_cart's existence check (via ProfileService)
    # passes by default in tests that don't care about that path. `cast` -- factory_boy's
    # DjangoModelFactory has no installed type stubs, so mypy infers CustomerFactory()'s
    # return type as the factory class itself, not Customer.
    customer_id = factory.LazyFunction(lambda: cast(Customer, CustomerFactory()).pk)
    # String-form SubFactory (factory_boy's own lazy-import mechanism) -- avoids a top-level
    # `from apps.branches.tests.factories import BranchFactory` in this module, the same
    # reasoning as `Cart.branch`'s lazy string FK (ADR 0004; see models/cart.py).
    branch = factory.SubFactory("apps.branches.tests.factories.BranchFactory")


class CartItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory("apps.products.tests.factories.ProductFactory")
    option_choice_ids = factory.LazyFunction(list)
    topping_ids = factory.LazyFunction(list)
    half_and_half = None
    quantity = 1
    note = ""
    unit_price_snapshot = Decimal("10.00")
