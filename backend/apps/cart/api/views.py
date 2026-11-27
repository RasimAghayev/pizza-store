from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.api.serializers import (
    CartItemCreateSerializer,
    CartItemQuantityUpdateSerializer,
    CartResponseSerializer,
)
from apps.cart.domain.branch_policy import DifferentBranchCartError
from apps.cart.services.cart_service import (
    BranchNotFoundError,
    CartItemNotFoundError,
    CartService,
    CustomerNotFoundError,
    ProductNotOrderableError,
)

# calls apps.customers.services.profile_service.ProfileService.get_profile() -- see
# backend/apps/customers/README.md. Resolves the authenticated identity.User to their own
# Customer row; cart never accepts a client-supplied customer_id in a request body (Issue
# #196 Security Requirements).
from apps.customers.services.profile_service import CustomerNotFoundError as ProfileNotFoundError
from apps.customers.services.profile_service import ProfileService


class _BranchConflict(exceptions.APIException):
    status_code = 409
    default_detail = "An open cart for a different branch already exists; clear it first."
    default_code = "conflict"


def _customer_id_for(request) -> int:
    try:
        return ProfileService().get_profile(request.user.pk).pk
    except ProfileNotFoundError as exc:
        raise exceptions.NotFound("Customer profile not found.") from exc


class CartView(APIView):
    """calls CartService -- see apps/cart/services/cart_service.py. GET/POST/DELETE all
    resolve the acting customer from `request.user`, never from a client-supplied id
    (Issue #196 Security Requirements)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        customer_id = _customer_id_for(request)
        priced = CartService().get_priced_active_cart(customer_id)
        return Response(CartResponseSerializer(priced).data)

    def post(self, request, version):
        customer_id = _customer_id_for(request)
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        try:
            CartService().add_item(
                customer_id=customer_id,
                branch_id=validated["branch_id"],
                product_id=validated.get("product_id"),
                option_choice_ids=validated.get("option_choice_ids"),
                topping_ids=validated.get("topping_ids"),
                half_and_half=validated.get("half_and_half"),
                quantity=validated["quantity"],
                note=validated["note"],
            )
        except BranchNotFoundError as exc:
            raise exceptions.NotFound("Branch not found.") from exc
        except DifferentBranchCartError as exc:
            raise _BranchConflict() from exc
        except ProductNotOrderableError as exc:
            raise exceptions.ValidationError(
                "This product is not orderable at this branch right now."
            ) from exc
        except CustomerNotFoundError as exc:
            raise exceptions.NotFound("Customer profile not found.") from exc

        priced = CartService().get_priced_active_cart(customer_id)
        return Response(CartResponseSerializer(priced).data, status=201)

    def delete(self, request, version):
        customer_id = _customer_id_for(request)
        CartService().clear(customer_id)
        return Response(status=204)


class CartItemDetailView(APIView):
    """calls CartService -- see apps/cart/services/cart_service.py. A valid item id owned
    by a different customer's cart returns 404, never 403 (Issue #196 Security
    Requirements, same pattern as apps.customers.api.views.AddressDetailView)."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, version, pk):
        customer_id = _customer_id_for(request)
        serializer = CartItemQuantityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            CartService().update_item_quantity(
                customer_id=customer_id,
                item_id=pk,
                quantity=serializer.validated_data["quantity"],
            )
        except CartItemNotFoundError as exc:
            raise exceptions.NotFound("Cart item not found.") from exc

        priced = CartService().get_priced_active_cart(customer_id)
        return Response(CartResponseSerializer(priced).data)

    def delete(self, request, version, pk):
        customer_id = _customer_id_for(request)
        try:
            CartService().remove_item(customer_id=customer_id, item_id=pk)
        except CartItemNotFoundError as exc:
            raise exceptions.NotFound("Cart item not found.") from exc

        priced = CartService().get_priced_active_cart(customer_id)
        return Response(CartResponseSerializer(priced).data)
