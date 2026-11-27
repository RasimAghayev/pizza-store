from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# calls apps.branches.services.branch_service.BranchService.get_by_id() -- see
# backend/apps/branches/README.md. Surfaced here only for BranchMenuView's existence check;
# menu never imports apps.branches.models/repositories directly.
from apps.branches.services.branch_service import BranchService
from apps.menu.api.serializers import (
    BranchMenuEntrySerializer,
    MenuCategoryCreateSerializer,
    MenuCategorySerializer,
    MenuCategoryUpdateSerializer,
    MenuItemCreateSerializer,
    MenuItemSerializer,
    MenuItemUpdateSerializer,
)
from apps.menu.models import MenuCategory, MenuItem
from apps.menu.services.menu_service import (
    BranchNotFoundError,
    CrossOrganizationMenuItemError,
    DuplicateMenuItemError,
    MenuCategoryNotFoundError,
    MenuService,
    ProductNotFoundError,
)
from shared.permissions.base import TwoStepPermission


class _ScopesToOwningBranch:
    """Shared scope hooks for MenuItem -- organization_id is re-derived through MenuService
    (which itself routes through BranchService, menu never imports apps.branches.models
    directly, ADR 0004); branch_id is the item's own branch, so a branch-scoped `menu.edit`
    grant can manage only that branch's items, while an org-scoped grant (e.g. Organization
    Owner) can manage every branch under its org."""

    def scope_organization_id(self, obj: MenuItem) -> int | None:
        return MenuService().organization_id_for_branch(obj.branch_id)

    def scope_branch_id(self, obj: MenuItem) -> int | None:
        return obj.branch_id


class _ScopesToOwningOrganization:
    """Shared scope hooks for MenuCategory -- organization-wide like Product's own catalog
    (Issue #181 precedent), never per-branch, so `scope_branch_id` always returns `None`."""

    def scope_organization_id(self, obj: MenuCategory) -> int | None:
        return obj.organization_id

    def scope_branch_id(self, obj: MenuCategory) -> int | None:
        return None


class BranchMenuView(APIView):
    """calls MenuService.menu_for_branch -- see apps/menu/services/menu_service.py. Public
    (AllowAny): the actual customer-facing menu listing (Issue #182's Implementation
    Prompt), same visibility as Branch/Product's own public read paths (Issues #180/#181).
    Mounted under `/api/v1/branches/<branch_id>/menu/` directly in config/urls.py -- not
    through `apps.branches.api.urls` -- so `apps.menu` stays the sole owner of this view and
    `apps.branches` never imports `apps.menu` (ADR 0004's dependency direction: menu depends
    on branches/products, never the reverse)."""

    permission_classes = [AllowAny]

    def get(self, request, version, branch_id):
        if BranchService().get_by_id(branch_id) is None:
            raise exceptions.NotFound("Branch not found.")
        items = MenuService().menu_for_branch(branch_id)
        return Response(BranchMenuEntrySerializer(items, many=True).data)


class MenuCategoryListCreateView(_ScopesToOwningOrganization, APIView):
    """calls MenuService.{list_categories_for_organization,create_category} -- see
    apps/menu/services/menu_service.py. Staff-only (ADR 0006 Context: like Organization,
    menu categories have no public/customer-facing read path of their own -- the public
    surface is the per-branch item listing above, not the category catalog itself).
    `required_permission` varies by method, same `@property` pattern as
    `OrganizationListCreateView` (Issue #180)."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "menu.edit" if self.request.method == "POST" else "menu.view"

    def get(self, request, version):
        raw_organization_id = request.query_params.get("organization_id")
        if raw_organization_id is None:
            raise exceptions.ValidationError({"organization_id": "Required."})
        try:
            organization_id = int(raw_organization_id)
        except ValueError as exc:
            raise exceptions.ValidationError({"organization_id": "Must be an integer."}) from exc

        provisional = MenuCategory(organization_id=organization_id)
        self.check_object_permissions(request, provisional)

        categories = MenuService().list_categories_for_organization(organization_id)
        return Response(MenuCategorySerializer(categories, many=True).data)

    def post(self, request, version):
        serializer = MenuCategoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provisional = MenuCategory(organization_id=serializer.validated_data["organization_id"])
        self.check_object_permissions(request, provisional)

        category = MenuService().create_category(**serializer.validated_data)
        return Response(MenuCategorySerializer(category).data, status=201)


class MenuCategoryDetailView(_ScopesToOwningOrganization, APIView):
    """calls MenuService -- see apps/menu/services/menu_service.py."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "menu.view" if self.request.method == "GET" else "menu.edit"

    def get(self, request, version, pk):
        category = self._require_category(request, pk)
        return Response(MenuCategorySerializer(category).data)

    def patch(self, request, version, pk):
        category = self._require_category(request, pk)
        serializer = MenuCategoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = MenuService().update_category(category.pk, **serializer.validated_data)
        return Response(MenuCategorySerializer(updated).data)

    def delete(self, request, version, pk):
        category = self._require_category(request, pk)
        MenuService().delete_category(category.pk)
        return Response(status=204)

    def _require_category(self, request, pk: int) -> MenuCategory:
        category = MenuService().get_category(pk)
        if category is None:
            raise exceptions.NotFound("Menu category not found.")
        self.check_object_permissions(request, category)
        return category


class MenuItemListCreateView(_ScopesToOwningBranch, APIView):
    """calls MenuService.{items_for_branch,create_item} -- see
    apps/menu/services/menu_service.py. Staff-only, unfiltered by availability -- this is
    "staff's own item list" from Issue #182's Test Requirement, distinct from the public,
    availability-filtered `BranchMenuView` above."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "menu.edit" if self.request.method == "POST" else "menu.view"

    def get(self, request, version):
        raw_branch_id = request.query_params.get("branch_id")
        if raw_branch_id is None:
            raise exceptions.ValidationError({"branch_id": "Required."})
        try:
            branch_id = int(raw_branch_id)
        except ValueError as exc:
            raise exceptions.ValidationError({"branch_id": "Must be an integer."}) from exc

        provisional = MenuItem(branch_id=branch_id)
        self.check_object_permissions(request, provisional)

        items = MenuService().items_for_branch(branch_id)
        return Response(MenuItemSerializer(items, many=True).data)

    def post(self, request, version):
        serializer = MenuItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provisional = MenuItem(branch_id=serializer.validated_data["branch_id"])
        self.check_object_permissions(request, provisional)

        try:
            item = MenuService().create_item(**serializer.validated_data)
        except BranchNotFoundError as exc:
            raise exceptions.ValidationError({"branch_id": "Branch not found."}) from exc
        except ProductNotFoundError as exc:
            raise exceptions.ValidationError({"product_id": "Product not found."}) from exc
        except MenuCategoryNotFoundError as exc:
            raise exceptions.ValidationError({"category_id": "Menu category not found."}) from exc
        except CrossOrganizationMenuItemError as exc:
            # A fixed, generic message -- never the raw exception text (CodeQL:
            # "information exposure through an exception") -- consistent with every other
            # translated domain error in this file.
            raise exceptions.ValidationError(
                {
                    "non_field_errors": (
                        "Product or category does not belong to this branch's organization."
                    )
                }
            ) from exc
        except DuplicateMenuItemError as exc:
            raise exceptions.ValidationError(
                {"product_id": "This product is already on this branch's menu."}
            ) from exc
        return Response(MenuItemSerializer(item).data, status=201)


class MenuItemDetailView(_ScopesToOwningBranch, APIView):
    """calls MenuService -- see apps/menu/services/menu_service.py."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "menu.view" if self.request.method == "GET" else "menu.edit"

    def get(self, request, version, pk):
        item = self._require_item(request, pk)
        return Response(MenuItemSerializer(item).data)

    def patch(self, request, version, pk):
        item = self._require_item(request, pk)
        serializer = MenuItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = MenuService().update_item(item.pk, **serializer.validated_data)
        except MenuCategoryNotFoundError as exc:
            raise exceptions.ValidationError({"category_id": "Menu category not found."}) from exc
        except CrossOrganizationMenuItemError as exc:
            raise exceptions.ValidationError(
                {"category_id": "Category does not belong to this item's organization."}
            ) from exc
        return Response(MenuItemSerializer(updated).data)

    def delete(self, request, version, pk):
        item = self._require_item(request, pk)
        MenuService().delete_item(item.pk)
        return Response(status=204)

    def _require_item(self, request, pk: int) -> MenuItem:
        item = MenuService().get_item(pk)
        if item is None:
            raise exceptions.NotFound("Menu item not found.")
        self.check_object_permissions(request, item)
        return item
