from decimal import Decimal

import pytest

from apps.products.services.catalog_service import AllergenNotFoundError, ToppingNotFoundError
from apps.products.services.product_service import (
    OptionGroupNotFoundError,
    ProductNotFoundError,
    ProductService,
)
from apps.products.tests.factories import AllergenFactory, ProductFactory, ToppingFactory
from apps.restaurants.services.organization_service import OrganizationNotFoundError
from apps.restaurants.tests.factories import OrganizationFactory


@pytest.mark.django_db
def test_create_raises_when_the_organization_does_not_exist():
    with pytest.raises(OrganizationNotFoundError):
        ProductService().create(
            organization_id=999_999, name="Margherita", base_price=Decimal("10.00")
        )


@pytest.mark.django_db
def test_create_persists_a_product_under_an_existing_organization():
    organization = OrganizationFactory()

    product = ProductService().create(
        organization_id=organization.pk, name="Margherita", base_price=Decimal("10.00")
    )

    assert product.pk is not None
    assert product.organization_id == organization.pk


@pytest.mark.django_db
def test_create_raises_when_an_allergen_id_does_not_exist():
    organization = OrganizationFactory()

    with pytest.raises(AllergenNotFoundError):
        ProductService().create(
            organization_id=organization.pk,
            name="Margherita",
            base_price=Decimal("10.00"),
            allergen_ids=[999_999],
        )


@pytest.mark.django_db
def test_list_for_organization_excludes_other_organizations_products():
    own_organization = OrganizationFactory()
    ProductFactory.create_batch(2, organization_id=own_organization.pk)
    ProductFactory()

    assert len(ProductService().list_for_organization(own_organization.pk)) == 2


@pytest.mark.django_db
def test_update_raises_when_the_product_does_not_exist():
    with pytest.raises(ProductNotFoundError):
        ProductService().update(999_999, name="New Name")


@pytest.mark.django_db
def test_delete_raises_when_the_product_does_not_exist():
    with pytest.raises(ProductNotFoundError):
        ProductService().delete(999_999)


@pytest.mark.django_db
def test_add_option_choice_raises_when_the_option_group_does_not_exist():
    with pytest.raises(OptionGroupNotFoundError):
        ProductService().add_option_choice(
            option_group_id=999_999, name="Large", price_delta=Decimal("3.00")
        )


@pytest.mark.django_db
def test_attach_topping_raises_when_the_topping_does_not_exist():
    product = ProductFactory()

    with pytest.raises(ToppingNotFoundError):
        ProductService().attach_topping(product_id=product.pk, topping_id=999_999)


@pytest.mark.django_db
def test_attaching_an_already_attached_topping_updates_its_flag_instead_of_erroring():
    product = ProductFactory()
    topping = ToppingFactory()

    ProductService().attach_topping(
        product_id=product.pk, topping_id=topping.pk, is_default_included=False
    )
    updated = ProductService().attach_topping(
        product_id=product.pk, topping_id=topping.pk, is_default_included=True
    )

    assert updated.is_default_included is True
    assert len(ProductService().toppings_for(product.pk)) == 1


@pytest.mark.django_db
def test_detach_topping_raises_when_not_attached():
    product = ProductFactory()
    topping = ToppingFactory()

    with pytest.raises(ToppingNotFoundError):
        ProductService().detach_topping(product_id=product.pk, topping_id=topping.pk)


@pytest.mark.django_db
def test_allergens_for_raises_when_the_product_does_not_exist():
    with pytest.raises(ProductNotFoundError):
        ProductService().allergens_for(999_999)


@pytest.mark.django_db
def test_allergens_for_unions_product_and_default_topping_allergens():
    product = ProductFactory()
    own_allergen = AllergenFactory(name="Gluten")
    product.allergens.set([own_allergen.pk])
    topping = ToppingFactory()
    topping_allergen = AllergenFactory(name="Dairy")
    topping.allergens.set([topping_allergen.pk])
    ProductService().attach_topping(
        product_id=product.pk, topping_id=topping.pk, is_default_included=True
    )

    names = {a.name for a in ProductService().allergens_for(product.pk)}

    assert names == {"Gluten", "Dairy"}


@pytest.mark.django_db
def test_add_option_group_and_choice_round_trip():
    product = ProductFactory()

    group = ProductService().add_option_group(product_id=product.pk, kind="size")
    choice = ProductService().add_option_choice(
        option_group_id=group.pk, name="Large", price_delta=Decimal("3.00")
    )

    assert choice.option_group_id == group.pk
    assert ProductService().option_groups_for(product.pk) == [group]
