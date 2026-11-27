import json
from types import SimpleNamespace
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.products.tests.factories import ProductFactory
from apps.restaurants.models import Organization
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory

ORGANIZATIONS_URL = "/api/v1/restaurants/organizations/"
RESTAURANTS_URL = "/api/v1/restaurants/"
BRANCHES_URL = "/api/v1/branches/"
PRODUCTS_URL = "/api/v1/products/"
MENU_URL = "/api/v1/menu/"


def _tenant() -> SimpleNamespace:
    """One organization with one restaurant/branch/product/menu-category/menu-item, all
    under the same organization -- mirrors
    apps/menu/tests/integration/test_menu_api.py::_branch_product_category_under_same_organization,
    extended with the menu item itself so every staff-facing resource this Phase built has a
    real row to assert isolation against."""
    # cast -- factory_boy's DjangoModelFactory has no installed type stubs, so mypy infers
    # OrganizationFactory()'s return type as the factory class itself, not Organization
    # (same reasoning as apps/products/tests/factories.py::ProductFactory).
    organization = cast(Organization, OrganizationFactory())
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    item = MenuItemFactory(branch=branch, product=product, category=category)
    return SimpleNamespace(
        organization=organization,
        restaurant=restaurant,
        branch=branch,
        product=product,
        category=category,
        item=item,
    )


def _authenticated(client, *, role_code: RoleCode, organization_id=None, branch_id=None):
    user = cast(User, UserFactory())
    RoleAssignmentRepository().create(
        user=user, role_code=role_code, organization_id=organization_id, branch_id=branch_id
    )
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return user


def _as_org_owner_of(client, tenant: SimpleNamespace):
    """ORGANIZATION_OWNER is the only non-Super-Admin role holding every org-scoped `.edit`
    permission this suite exercises (restaurants.edit, products.edit, menu.edit) -- using it
    as the acting role proves TwoStepPermission's step-2 *scope* check specifically, not just
    step-1 permission absence (apps/identity/domain/rbac.py::ROLE_PERMISSIONS)."""
    return _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=tenant.organization.pk
    )


def _as_branch_manager_of(client, tenant: SimpleNamespace):
    return _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=tenant.branch.pk)


def _patch_json(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type="application/json")


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def two_tenants(db):
    return _tenant(), _tenant()


@pytest.mark.django_db
@pytest.mark.parametrize("acting_idx,target_idx", [(0, 1), (1, 0)])
class TestOrganizationScopedWriteIsolation:
    """Epic #14's multi-tenant isolation Acceptance Criterion, exercised against every
    org-scoped staff resource this Phase built (restaurants, products, menu categories) --
    Issue #180's own suite already proves this for Organization/Branch in isolation; this
    suite proves it holds across the full set, in both directions."""

    def test_organization_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = _patch_json(
            client,
            f"{ORGANIZATIONS_URL}{tenants[target_idx].organization.pk}/",
            {"name": "Hijacked"},
        )

        assert response.status_code == 403

    def test_organization_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.delete(f"{ORGANIZATIONS_URL}{tenants[target_idx].organization.pk}/")

        assert response.status_code == 403

    def test_organization_list_is_scoped_to_the_callers_own_organization(
        self, client, two_tenants, acting_idx, target_idx
    ):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.get(ORGANIZATIONS_URL)

        assert response.status_code == 200
        visible_ids = {row["id"] for row in response.json()}
        assert tenants[acting_idx].organization.pk in visible_ids
        assert tenants[target_idx].organization.pk not in visible_ids

    def test_restaurant_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = _patch_json(
            client, f"{RESTAURANTS_URL}{tenants[target_idx].restaurant.pk}/", {"name": "Hijacked"}
        )

        assert response.status_code == 403

    def test_restaurant_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.delete(f"{RESTAURANTS_URL}{tenants[target_idx].restaurant.pk}/")

        assert response.status_code == 403

    def test_product_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = _patch_json(
            client, f"{PRODUCTS_URL}{tenants[target_idx].product.pk}/", {"name": "Hijacked"}
        )

        assert response.status_code == 403

    def test_product_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.delete(f"{PRODUCTS_URL}{tenants[target_idx].product.pk}/")

        assert response.status_code == 403

    def test_product_option_group_create(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = _post_json(
            client,
            f"{PRODUCTS_URL}{tenants[target_idx].product.pk}/option-groups/",
            {"kind": "size"},
        )

        assert response.status_code == 403

    def test_menu_category_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = _patch_json(
            client,
            f"{MENU_URL}categories/{tenants[target_idx].category.pk}/",
            {"name": "Hijacked"},
        )

        assert response.status_code == 403

    def test_menu_category_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.delete(f"{MENU_URL}categories/{tenants[target_idx].category.pk}/")

        assert response.status_code == 403

    def test_menu_category_read(self, client, two_tenants, acting_idx, target_idx):
        """MenuCategory, unlike Product/Restaurant/Branch, has no public read path (ADR
        0006 Context) -- a cross-org `GET` is denied at the same step 2 check as a write."""
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.get(f"{MENU_URL}categories/{tenants[target_idx].category.pk}/")

        assert response.status_code == 403

    def test_menu_category_list_rejects_a_foreign_organization_id(
        self, client, two_tenants, acting_idx, target_idx
    ):
        tenants = two_tenants
        _as_org_owner_of(client, tenants[acting_idx])

        response = client.get(
            f"{MENU_URL}categories/?organization_id={tenants[target_idx].organization.pk}"
        )

        assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("acting_idx,target_idx", [(0, 1), (1, 0)])
class TestBranchScopedWriteIsolation:
    """Mirrors TestOrganizationScopedWriteIsolation for the branch-scoped half of the Epic's
    resource set (branches themselves, and menu items -- the one resource whose scope is its
    own branch rather than its organization, Issue #182's `_ScopesToOwningBranch`)."""

    def test_branch_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = _patch_json(
            client, f"{BRANCHES_URL}{tenants[target_idx].branch.pk}/", {"capacity": 999}
        )

        assert response.status_code == 403

    def test_branch_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = client.delete(f"{BRANCHES_URL}{tenants[target_idx].branch.pk}/")

        assert response.status_code == 403

    def test_branch_hours_create(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = _post_json(
            client,
            f"{BRANCHES_URL}{tenants[target_idx].branch.pk}/hours/",
            {"weekday": 0, "opens_at": "09:00", "closes_at": "22:00"},
        )

        assert response.status_code == 403

    def test_branch_closure_create(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = _post_json(
            client,
            f"{BRANCHES_URL}{tenants[target_idx].branch.pk}/closures/",
            {"starts_at": "2026-12-01T00:00:00Z", "ends_at": "2026-12-02T00:00:00Z"},
        )

        assert response.status_code == 403

    def test_menu_item_update(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = _patch_json(
            client, f"{MENU_URL}items/{tenants[target_idx].item.pk}/", {"display_order": 5}
        )

        assert response.status_code == 403

    def test_menu_item_delete(self, client, two_tenants, acting_idx, target_idx):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = client.delete(f"{MENU_URL}items/{tenants[target_idx].item.pk}/")

        assert response.status_code == 403

    def test_menu_item_read(self, client, two_tenants, acting_idx, target_idx):
        """MenuItemDetailView requires `menu.view` at step 1 and the item's own branch at
        step 2 even for `GET` -- unlike BranchMenuView (the public, availability-filtered
        customer listing), this is staff's own item view (Issue #182's Test Requirement)."""
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = client.get(f"{MENU_URL}items/{tenants[target_idx].item.pk}/")

        assert response.status_code == 403

    def test_menu_item_list_rejects_a_foreign_branch_id(
        self, client, two_tenants, acting_idx, target_idx
    ):
        tenants = two_tenants
        _as_branch_manager_of(client, tenants[acting_idx])

        response = client.get(f"{MENU_URL}items/?branch_id={tenants[target_idx].branch.pk}")

        assert response.status_code == 403


@pytest.mark.django_db
def test_super_admin_is_exempt_from_every_scope_check_above(client):
    """Sanity check that the 403s above are the scope check, not some unrelated permission
    failure -- an unscoped grant (Super Admin) must pass every one of them, per
    TwoStepPermission.has_object_permission's `organization_id is None and branch_id is None`
    branch (shared/permissions/base.py)."""
    tenant = _tenant()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    responses = [
        _patch_json(client, f"{ORGANIZATIONS_URL}{tenant.organization.pk}/", {"name": "Ok"}),
        _patch_json(client, f"{RESTAURANTS_URL}{tenant.restaurant.pk}/", {"name": "Ok"}),
        _patch_json(client, f"{BRANCHES_URL}{tenant.branch.pk}/", {"capacity": 60}),
        _patch_json(client, f"{PRODUCTS_URL}{tenant.product.pk}/", {"name": "Ok"}),
        _patch_json(client, f"{MENU_URL}categories/{tenant.category.pk}/", {"name": "Ok"}),
        _patch_json(client, f"{MENU_URL}items/{tenant.item.pk}/", {"display_order": 1}),
    ]

    assert [r.status_code for r in responses] == [200, 200, 200, 200, 200, 200]
