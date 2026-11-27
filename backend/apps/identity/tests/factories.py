import factory
from faker import Faker

from apps.identity.domain.rbac import RoleCode
from apps.identity.models import RoleAssignment, User

fake = Faker()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyFunction(fake.email)

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or fake.password())


class RoleAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RoleAssignment

    user = factory.SubFactory(UserFactory)
    role_code = RoleCode.CUSTOMER
    organization_id = None
    branch_id = None
