import factory

from apps.customers.models.address import Address
from apps.customers.models.customer import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    user_id = factory.Sequence(lambda n: n + 1)


class AddressFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Address

    customer = factory.SubFactory(CustomerFactory)
    label = "Home"
    street_and_unit = "123 Main St, Apt 4B"
    city = "Springfield"
    postal_code = "12345"
