from decimal import Decimal
from typing import cast

import factory

from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.orders.models import Order, OrderItem


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    # Plain field, not a SubFactory -- Order.customer_id carries no cross-app FK (ADR 0004;
    # see models/order.py), same reasoning as Issue #196's Cart.customer_id. `cast` --
    # factory_boy's DjangoModelFactory has no installed type stubs, so mypy infers
    # CustomerFactory()'s return type as the factory class itself, not Customer.
    customer_id = factory.LazyFunction(lambda: cast(Customer, CustomerFactory()).pk)
    # String-form SubFactory (factory_boy's own lazy-import mechanism) -- avoids a top-level
    # `from apps.branches.tests.factories import BranchFactory` in this module, same
    # reasoning as `Order.branch`'s lazy string FK (ADR 0004; see models/order.py).
    branch = factory.SubFactory("apps.branches.tests.factories.BranchFactory")
    status = "pending_payment"
    subtotal = Decimal("10.00")
    delivery_fee = Decimal("2.50")
    discount_amount = Decimal("0.00")
    total_amount = Decimal("12.50")
    delivery_street_and_unit = "123 Main St, Apt 4B"
    delivery_city = "Springfield"
    delivery_postal_code = "12345"
    idempotency_key = factory.Sequence(lambda n: f"order-factory-key-{n}")


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product_id = factory.Sequence(lambda n: n + 1)
    name = "Margherita"
    selection = factory.LazyFunction(dict)
    unit_price = Decimal("10.00")
    quantity = 1
    line_total = Decimal("10.00")
