import factory
from faker import Faker

from apps.identity.models import User

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyFunction(fake.email)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or fake.password())
