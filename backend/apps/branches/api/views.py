from decimal import Decimal, InvalidOperation

from rest_framework import exceptions
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.branches.api.serializers import (
    BranchClosureCreateSerializer,
    BranchClosureSerializer,
    BranchCreateSerializer,
    BranchSerializer,
    BranchUpdateSerializer,
    BusinessHoursSerializer,
    BusinessHoursWriteSerializer,
)
from apps.branches.models import Branch
from apps.branches.services.branch_service import (
    BranchNotFoundError,
    BranchService,
    ClosureNotFoundError,
)

# calls apps.restaurants.services.restaurant_service.RestaurantNotFoundError -- see
# backend/apps/restaurants/README.md. Surfaced here only to translate it into the standard
# validation_error envelope; branches never imports apps.restaurants.models/repositories.
from apps.restaurants.services.restaurant_service import RestaurantNotFoundError
from shared.permissions.base import TwoStepPermission


class _ScopesToOwningOrganization:
    """Shared scope hooks for every Branch-nested view below -- Branch itself has no
    `organization_id` column (see BranchService.organization_id_for_restaurant); `branch_id`
    is always the Branch's own id, since every nested resource (hours/closures) is scoped to
    exactly one branch, never to the whole organization."""

    def scope_organization_id(self, obj: Branch) -> int | None:
        return BranchService().organization_id_for_restaurant(obj.restaurant_id)

    def scope_branch_id(self, obj: Branch) -> int | None:
        return obj.pk


class BranchListCreateView(_ScopesToOwningOrganization, APIView):
    """calls BranchService -- see apps/branches/services/branch_service.py. Read is public
    (AllowAny) -- menu-browsing needs this before login exists, Issue #180's Implementation
    Prompt."""

    required_permission = "branches.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version):
        branches = BranchService().list_all()
        return Response(BranchSerializer(branches, many=True).data)

    def post(self, request, version):
        serializer = BranchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provisional = Branch(restaurant_id=serializer.validated_data["restaurant_id"])
        self.check_object_permissions(request, provisional)

        try:
            branch = BranchService().create(**serializer.validated_data)
        except RestaurantNotFoundError as exc:
            raise exceptions.ValidationError({"restaurant_id": "Restaurant not found."}) from exc
        return Response(BranchSerializer(branch).data, status=201)


class BranchNearbyView(APIView):
    """calls BranchService.within_delivery_radius_of -- public (AllowAny), same read
    visibility as BranchListCreateView."""

    permission_classes = [AllowAny]

    def get(self, request, version):
        try:
            latitude = request.query_params["lat"]
            longitude = request.query_params["lon"]
        except KeyError as exc:
            raise exceptions.ValidationError({"lat": "Required.", "lon": "Required."}) from exc

        try:
            latitude_decimal = Decimal(latitude)
            longitude_decimal = Decimal(longitude)
        except InvalidOperation as exc:
            raise exceptions.ValidationError(
                {"lat": "Must be a decimal number.", "lon": "Must be a decimal number."}
            ) from exc

        branches = BranchService().within_delivery_radius_of(
            latitude=latitude_decimal, longitude=longitude_decimal
        )
        return Response(BranchSerializer(branches, many=True).data)


class BranchDetailView(_ScopesToOwningOrganization, APIView):
    """calls BranchService -- see apps/branches/services/branch_service.py."""

    required_permission = "branches.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        branch = BranchService().get_by_id(pk)
        if branch is None:
            raise exceptions.NotFound("Branch not found.")
        return Response(BranchSerializer(branch).data)

    def patch(self, request, version, pk):
        branch = self._get_object_for_write(request, pk)
        serializer = BranchUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = BranchService().update(branch.pk, **serializer.validated_data)
        return Response(BranchSerializer(updated).data)

    def delete(self, request, version, pk):
        branch = self._get_object_for_write(request, pk)
        BranchService().delete(branch.pk)
        return Response(status=204)

    def _get_object_for_write(self, request, pk: int) -> Branch:
        branch = BranchService().get_by_id(pk)
        if branch is None:
            raise exceptions.NotFound("Branch not found.")
        self.check_object_permissions(request, branch)
        return branch


class BranchIsOpenView(APIView):
    """calls BranchService.is_open_now -- public (AllowAny): customers need this to decide
    whether to order, same visibility as the branch listing itself."""

    permission_classes = [AllowAny]

    def get(self, request, version, pk):
        try:
            is_open = BranchService().is_open_now(pk)
        except BranchNotFoundError as exc:
            raise exceptions.NotFound("Branch not found.") from exc
        return Response({"is_open": is_open})


class BranchHoursView(_ScopesToOwningOrganization, APIView):
    """calls BranchService.{set_hours,hours_for} -- see
    apps/branches/services/branch_service.py. Read is public (AllowAny); only setting hours
    requires the branch's `branches.edit` scope."""

    required_permission = "branches.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        branch = self._require_branch(pk)
        hours = BranchService().hours_for(branch.pk)
        return Response(BusinessHoursSerializer(hours, many=True).data)

    def post(self, request, version, pk):
        branch = self._require_branch(pk)
        self.check_object_permissions(request, branch)
        serializer = BusinessHoursWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = BranchService().set_hours(branch_id=branch.pk, **serializer.validated_data)
        return Response(BusinessHoursSerializer(row).data, status=201)

    @staticmethod
    def _require_branch(pk: int) -> Branch:
        branch = BranchService().get_by_id(pk)
        if branch is None:
            raise exceptions.NotFound("Branch not found.")
        return branch


class BranchClosuresView(_ScopesToOwningOrganization, APIView):
    """calls BranchService.{add_closure,closures_for} -- see
    apps/branches/services/branch_service.py. Read is public (AllowAny); only creating a
    closure requires the branch's `branches.edit` scope."""

    required_permission = "branches.edit"

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [TwoStepPermission()]

    def get(self, request, version, pk):
        branch = self._require_branch(pk)
        closures = BranchService().closures_for(branch.pk)
        return Response(BranchClosureSerializer(closures, many=True).data)

    def post(self, request, version, pk):
        branch = self._require_branch(pk)
        self.check_object_permissions(request, branch)
        serializer = BranchClosureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closure = BranchService().add_closure(branch_id=branch.pk, **serializer.validated_data)
        return Response(BranchClosureSerializer(closure).data, status=201)

    @staticmethod
    def _require_branch(pk: int) -> Branch:
        branch = BranchService().get_by_id(pk)
        if branch is None:
            raise exceptions.NotFound("Branch not found.")
        return branch


class BranchClosureDetailView(_ScopesToOwningOrganization, APIView):
    """calls BranchService.delete_closure -- see apps/branches/services/branch_service.py."""

    required_permission = "branches.edit"
    permission_classes = [TwoStepPermission]

    def delete(self, request, version, pk, closure_id):
        branch = BranchService().get_by_id(pk)
        if branch is None:
            raise exceptions.NotFound("Branch not found.")
        self.check_object_permissions(request, branch)
        try:
            BranchService().delete_closure(closure_id)
        except ClosureNotFoundError as exc:
            raise exceptions.NotFound("Closure not found.") from exc
        return Response(status=204)
