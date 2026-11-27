import factory
from faker import Faker

from health.models import HealthPing

fake = Faker()


class HealthPingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HealthPing

    note = factory.LazyFunction(fake.sentence)
