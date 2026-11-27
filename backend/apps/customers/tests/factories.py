import factory

from apps.customers.models.customer import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    user_id = factory.Sequence(lambda n: n + 1)
