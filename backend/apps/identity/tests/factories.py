import factory
from faker import Faker

from apps.identity.models import User

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyFunction(fake.email)
    password = factory.PostGenerationMethodCall("set_password", "Str0ngP@ssw0rd!")
