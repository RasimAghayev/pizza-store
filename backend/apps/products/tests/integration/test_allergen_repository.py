import pytest

from apps.products.repositories.allergen_repository import AllergenRepository
from apps.products.tests.factories import AllergenFactory, ProductFactory, ToppingFactory


@pytest.mark.django_db
def test_union_includes_the_products_own_allergens():
    product = ProductFactory()
    allergen = AllergenFactory(name="Gluten")
    product.allergens.set([allergen.pk])

    result = AllergenRepository().for_product_union_default_toppings(product)

    assert [a.name for a in result] == ["Gluten"]


@pytest.mark.django_db
def test_union_includes_default_included_toppings_allergens():
    product = ProductFactory()
    topping = ToppingFactory()
    allergen = AllergenFactory(name="Dairy")
    topping.allergens.set([allergen.pk])
    product.product_toppings.create(topping=topping, is_default_included=True)

    result = AllergenRepository().for_product_union_default_toppings(product)

    assert [a.name for a in result] == ["Dairy"]


@pytest.mark.django_db
def test_union_excludes_optional_non_default_toppings_allergens():
    product = ProductFactory()
    topping = ToppingFactory()
    allergen = AllergenFactory(name="Shellfish")
    topping.allergens.set([allergen.pk])
    product.product_toppings.create(topping=topping, is_default_included=False)

    result = AllergenRepository().for_product_union_default_toppings(product)

    assert result == []


@pytest.mark.django_db
def test_union_deduplicates_an_allergen_shared_by_product_and_a_default_topping():
    product = ProductFactory()
    allergen = AllergenFactory(name="Gluten")
    product.allergens.set([allergen.pk])
    topping = ToppingFactory()
    topping.allergens.set([allergen.pk])
    product.product_toppings.create(topping=topping, is_default_included=True)

    result = AllergenRepository().for_product_union_default_toppings(product)

    assert [a.name for a in result] == ["Gluten"]
