from datetime import time

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.menu.services.menu_service import (
    BranchNotFoundError,
    CrossOrganizationMenuItemError,
    DuplicateMenuItemError,
    MenuCategoryNotFoundError,
    MenuItemNotFoundError,
    MenuService,
    ProductNotFoundError,
)
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory


def _branch_product_category_under_same_organization():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    return branch, product, category


@pytest.mark.django_db
def test_create_item_raises_when_the_branch_does_not_exist():
    _, product, category = _branch_product_category_under_same_organization()

    with pytest.raises(BranchNotFoundError):
        MenuService().create_item(branch_id=999_999, product_id=product.pk, category_id=category.pk)


@pytest.mark.django_db
def test_create_item_raises_when_the_product_does_not_exist():
    branch, _, category = _branch_product_category_under_same_organization()

    with pytest.raises(ProductNotFoundError):
        MenuService().create_item(branch_id=branch.pk, product_id=999_999, category_id=category.pk)


@pytest.mark.django_db
def test_create_item_raises_when_the_category_does_not_exist():
    branch, product, _ = _branch_product_category_under_same_organization()

    with pytest.raises(MenuCategoryNotFoundError):
        MenuService().create_item(branch_id=branch.pk, product_id=product.pk, category_id=999_999)


@pytest.mark.django_db
def test_create_item_raises_when_the_product_belongs_to_a_different_organization():
    branch, _, category = _branch_product_category_under_same_organization()
    other_product = ProductFactory()

    with pytest.raises(CrossOrganizationMenuItemError):
        MenuService().create_item(
            branch_id=branch.pk, product_id=other_product.pk, category_id=category.pk
        )


@pytest.mark.django_db
def test_create_item_raises_when_the_category_belongs_to_a_different_organization():
    branch, product, _ = _branch_product_category_under_same_organization()
    other_category = MenuCategoryFactory()

    with pytest.raises(CrossOrganizationMenuItemError):
        MenuService().create_item(
            branch_id=branch.pk, product_id=product.pk, category_id=other_category.pk
        )


@pytest.mark.django_db
def test_create_item_persists_a_consistent_item():
    branch, product, category = _branch_product_category_under_same_organization()

    item = MenuService().create_item(
        branch_id=branch.pk, product_id=product.pk, category_id=category.pk
    )

    assert item.pk is not None
    assert item.branch_id == branch.pk
    assert item.product_id == product.pk


@pytest.mark.django_db
def test_create_item_raises_on_a_duplicate_branch_product_pair():
    branch, product, category = _branch_product_category_under_same_organization()
    MenuService().create_item(branch_id=branch.pk, product_id=product.pk, category_id=category.pk)

    with pytest.raises(DuplicateMenuItemError):
        MenuService().create_item(
            branch_id=branch.pk, product_id=product.pk, category_id=category.pk
        )


@pytest.mark.django_db
def test_update_item_raises_when_the_item_does_not_exist():
    with pytest.raises(MenuItemNotFoundError):
        MenuService().update_item(999_999, display_order=1)


@pytest.mark.django_db
def test_update_item_raises_when_the_new_category_belongs_to_a_different_organization():
    item = MenuItemFactory()
    other_category = MenuCategoryFactory()

    with pytest.raises(CrossOrganizationMenuItemError):
        MenuService().update_item(item.pk, category_id=other_category.pk)


@pytest.mark.django_db
def test_delete_item_raises_when_the_item_does_not_exist():
    with pytest.raises(MenuItemNotFoundError):
        MenuService().delete_item(999_999)


@pytest.mark.django_db
def test_delete_category_raises_when_the_category_does_not_exist():
    with pytest.raises(MenuCategoryNotFoundError):
        MenuService().delete_category(999_999)


@pytest.mark.django_db
def test_menu_for_branch_does_not_leak_another_branchs_item():
    """Issue #182's own Test Requirement -- the first real proof that one branch's menu
    does not depend on another's (master prompt §11)."""
    branch_a, product, category = _branch_product_category_under_same_organization()
    branch_b = BranchFactory()
    MenuService().create_item(branch_id=branch_a.pk, product_id=product.pk, category_id=category.pk)

    assert len(MenuService().menu_for_branch(branch_a.pk)) == 1
    assert MenuService().menu_for_branch(branch_b.pk) == []


@pytest.mark.django_db
def test_menu_for_branch_excludes_an_item_outside_its_availability_window():
    item = MenuItemFactory(available_from=time(11, 0), available_until=time(14, 0))

    assert MenuService().menu_for_branch(item.branch_id, at=time(20, 0)) == []
    assert len(MenuService().menu_for_branch(item.branch_id, at=time(12, 0))) == 1


@pytest.mark.django_db
def test_set_availability_false_removes_the_item_from_the_public_listing_but_not_staff_list():
    item = MenuItemFactory(is_available=True)

    MenuService().set_availability(item.pk, False)

    assert MenuService().menu_for_branch(item.branch_id) == []
    staff_items = MenuService().items_for_branch(item.branch_id)
    assert len(staff_items) == 1
    assert staff_items[0].is_available is False
