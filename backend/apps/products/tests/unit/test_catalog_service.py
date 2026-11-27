from decimal import Decimal

import pytest

from apps.products.services.catalog_service import (
    AllergenNotFoundError,
    CatalogService,
    ToppingNotFoundError,
)
from apps.products.tests.factories import AllergenFactory, ToppingFactory


@pytest.mark.django_db
def test_create_topping_raises_when_an_allergen_id_does_not_exist():
    with pytest.raises(AllergenNotFoundError):
        CatalogService().create_topping(
            name="Pepperoni", price_delta=Decimal("1.50"), allergen_ids=[999_999]
        )


@pytest.mark.django_db
def test_create_topping_persists_its_sku_reference():
    topping = CatalogService().create_topping(
        name="Pepperoni", price_delta=Decimal("1.50"), sku_reference="SKU-1"
    )

    assert topping.sku_reference == "SKU-1"


@pytest.mark.django_db
def test_update_topping_raises_when_it_does_not_exist():
    with pytest.raises(ToppingNotFoundError):
        CatalogService().update_topping(999_999, name="Renamed")


@pytest.mark.django_db
def test_delete_topping_raises_when_it_does_not_exist():
    with pytest.raises(ToppingNotFoundError):
        CatalogService().delete_topping(999_999)


@pytest.mark.django_db
def test_delete_allergen_raises_when_it_does_not_exist():
    with pytest.raises(AllergenNotFoundError):
        CatalogService().delete_allergen(999_999)


@pytest.mark.django_db
def test_list_toppings_and_allergens_return_every_row():
    ToppingFactory.create_batch(2)
    AllergenFactory.create_batch(3)

    assert len(CatalogService().list_toppings()) == 2
    assert len(CatalogService().list_allergens()) == 3
