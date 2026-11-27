import factory

from apps.restaurants.models import Organization, Restaurant


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Organization {n}")
    owner_user_id = factory.Sequence(lambda n: n + 1)


class RestaurantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Restaurant

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Restaurant {n}")
    description = ""
