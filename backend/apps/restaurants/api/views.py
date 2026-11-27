from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.restaurants.api.serializers import (
    OrganizationCreateSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
    RestaurantCreateSerializer,
    RestaurantSerializer,
    RestaurantUpdateSerializer,
)
from apps.restaurants.models import Organization, Restaurant
from apps.restaurants.services.organization_service import (
    OrganizationNotFoundError,
    OrganizationService,
)
from apps.restaurants.services.restaurant_service import RestaurantService
from shared.permissions.base import TwoStepPermission


class OrganizationListCreateView(APIView):
    """calls OrganizationService -- see apps/restaurants/services/organization_service.py.
    Staff-only (ADR 0006 Context: Organization has no public/customer-facing read path,
    unlike Restaurant/Branch). `TwoStepPermission` reads `required_permission` off *this
    view* (see shared/permissions/base.py), not off a BasePermission subclass -- a
    `@property` lets it vary by HTTP method within one view."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "restaurants.edit" if self.request.method == "POST" else "restaurants.view"

    def get(self, request, version):
        organizations = OrganizationService().list_visible_to(request.user)
        data = OrganizationSerializer(organizations, many=True).data
        return Response(data)

    def post(self, request, version):
        serializer = OrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # No saved Organization exists yet to re-derive scope from -- a provisional,
        # unsaved instance lets step 2 apply the same scope rule anyway: its own `pk` is
        # `None`, which only an unscoped assignment (e.g. Super Admin) can match (see
        # shared/permissions/base.py::TwoStepPermission.has_object_permission), so an
        # org-scoped or branch-scoped holder of `restaurants.edit` cannot create a brand
        # new Organization through this path.
        provisional = Organization(**serializer.validated_data)
        self.check_object_permissions(request, provisional)

        organization = OrganizationService().create(**serializer.validated_data)
        return Response(OrganizationSerializer(organization).data, status=201)

    @staticmethod
    def scope_organization_id(obj: Organization) -> int | None:
        return obj.pk

    @staticmethod
    def scope_branch_id(obj: Organization) -> int | None:
        return None


class OrganizationDetailView(APIView):
    """calls OrganizationService -- see apps/restaurants/services/organization_service.py."""

    permission_classes = [TwoStepPermission]

    @property
    def required_permission(self) -> str:
        return "restaurants.view" if self.request.method == "GET" else "restaurants.edit"

    def get(self, request, version, pk):
        organization = self._get_object(request, pk)
        return Response(OrganizationSerializer(organization).data)

    def patch(self, request, version, pk):
        organization = self._get_object(request, pk)
        serializer = OrganizationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = OrganizationService().update(organization.pk, **serializer.validated_data)
        return Response(OrganizationSerializer(updated).data)

    def delete(self, request, version, pk):
        organization = self._get_object(request, pk)
        OrganizationService().delete(organization.pk)
        return Response(status=204)

    def _get_object(self, request, pk: int) -> Organization:
        organization = OrganizationService().get_by_id(pk)
        if organization is None:
            raise exceptions.NotFound("Organization not found.")
        self.check_object_permissions(request, organization)
        return organization

    @staticmethod
    def scope_organization_id(obj: Organization) -> int | None:
        return obj.pk

    @staticmethod
    def scope_branch_id(obj: Organization) -> int | None:
        return None


class RestaurantListCreateView(APIView):
    """calls RestaurantService -- see apps/restaurants/services/restaurant_service.py. Read
    is public (AllowAny) -- menu-browsing needs this before login exists, Issue #180's
    Implementation Prompt."""

    required_permission = "restaurants.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version):
        restaurants = RestaurantService().list_all()
        return Response(RestaurantSerializer(restaurants, many=True).data)

    def post(self, request, version):
        serializer = RestaurantCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provisional = Restaurant(organization_id=serializer.validated_data["organization_id"])
        self.check_object_permissions(request, provisional)

        try:
            restaurant = RestaurantService().create(**serializer.validated_data)
        except OrganizationNotFoundError as exc:
            raise exceptions.ValidationError(
                {"organization_id": "Organization not found."}
            ) from exc
        return Response(RestaurantSerializer(restaurant).data, status=201)

    @staticmethod
    def scope_organization_id(obj: Restaurant) -> int | None:
        return obj.organization_id

    @staticmethod
    def scope_branch_id(obj: Restaurant) -> int | None:
        return None


class RestaurantDetailView(APIView):
    """calls RestaurantService -- see apps/restaurants/services/restaurant_service.py."""

    required_permission = "restaurants.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        restaurant = RestaurantService().get_by_id(pk)
        if restaurant is None:
            raise exceptions.NotFound("Restaurant not found.")
        return Response(RestaurantSerializer(restaurant).data)

    def patch(self, request, version, pk):
        restaurant = self._get_object_for_write(request, pk)
        serializer = RestaurantUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = RestaurantService().update(restaurant.pk, **serializer.validated_data)
        return Response(RestaurantSerializer(updated).data)

    def delete(self, request, version, pk):
        restaurant = self._get_object_for_write(request, pk)
        RestaurantService().delete(restaurant.pk)
        return Response(status=204)

    def _get_object_for_write(self, request, pk: int) -> Restaurant:
        restaurant = RestaurantService().get_by_id(pk)
        if restaurant is None:
            raise exceptions.NotFound("Restaurant not found.")
        self.check_object_permissions(request, restaurant)
        return restaurant

    @staticmethod
    def scope_organization_id(obj: Restaurant) -> int | None:
        return obj.organization_id

    @staticmethod
    def scope_branch_id(obj: Restaurant) -> int | None:
        return None
