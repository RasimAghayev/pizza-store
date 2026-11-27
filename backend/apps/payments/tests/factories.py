from decimal import Decimal
from typing import cast

import factory

from apps.orders.models import Order
from apps.orders.tests.factories import OrderFactory
from apps.payments.models import Payment


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    # Plain field, not a SubFactory -- Payment.order_id carries no cross-app FK (ADR 0004; see
    # models/payment.py), same reasoning as Order.customer_id. `cast` -- factory_boy's
    # DjangoModelFactory has no installed type stubs, so mypy infers OrderFactory()'s return
    # type as the factory class itself, not Order.
    order_id = factory.LazyFunction(lambda: cast(Order, OrderFactory()).pk)
    gateway = "cash_on_delivery"
    amount = Decimal("12.50")
    currency = "USD"
    status = "captured"
    provider_reference = "cash_on_delivery"
    idempotency_key = factory.Sequence(lambda n: f"payment-factory-key-{n}")
