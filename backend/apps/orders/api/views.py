from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# calls apps.cart.services.cart_service.CartService.get_active_cart() -- see
# backend/apps/cart/README.md. Resolves the customer's own active cart server-side so a
# checkout request never accepts a client-supplied cart id (Issue #197 Security
# Requirements).
from apps.cart.services.cart_service import CartService

# calls apps.customers.services.profile_service.ProfileService.get_profile() -- see
# backend/apps/customers/README.md. Resolves the authenticated identity.User to their own
# Customer row; orders never accepts a client-supplied customer_id in a request body (same
# pattern as apps.cart.api.views._customer_id_for).
from apps.customers.services.profile_service import CustomerNotFoundError as ProfileNotFoundError
from apps.customers.services.profile_service import ProfileService
from apps.orders.api.serializers import CheckoutRequestSerializer, OrderResponseSerializer
from apps.orders.services.order_service import (
    AddressNotFoundError,
    BelowMinimumOrderAmountError,
    BranchNotFoundError,
    CartNotFoundError,
    OrderNotFoundError,
    OrderService,
)
from shared.idempotency.drf import IdempotentActionMixin


def _customer_id_for(request) -> int:
    try:
        return ProfileService().get_profile(request.user.pk).pk
    except ProfileNotFoundError as exc:
        raise exceptions.NotFound("Customer profile not found.") from exc


class CheckoutView(IdempotentActionMixin, APIView):
    """calls OrderService.checkout() -- see apps/orders/services/order_service.py. Unlike
    `IdempotentActionMixin`'s own per-view-optional default, the `Idempotency-Key` header is
    MANDATORY here and rejected before `perform_idempotent` is even called -- Issue #197
    Technical Context names checkout as exactly the endpoint the Epic #15 duplicate-submission
    acceptance test targets."""

    permission_classes = [IsAuthenticated]

    def post(self, request, version):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise exceptions.ValidationError(
                {"Idempotency-Key": "This header is required for checkout."}
            )

        customer_id = _customer_id_for(request)
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address_id = serializer.validated_data["address_id"]

        def handler() -> tuple[int, object]:
            # Resolved inside the handler, not before `perform_idempotent` is called: a
            # duplicate request replays the FIRST request's cached response without ever
            # invoking this closure, so a cart already cleared by that first checkout must
            # not make a replay look like a fresh, empty-cart request (Issue #197).
            cart = CartService().get_active_cart(customer_id)
            if cart is None:
                raise exceptions.ValidationError("Your cart is empty.")
            try:
                order = OrderService().checkout(
                    customer_id=customer_id,
                    cart_id=cart.pk,
                    address_id=address_id,
                    idempotency_key=idempotency_key,
                )
            except CartNotFoundError as exc:
                raise exceptions.ValidationError("Your cart is empty.") from exc
            except BranchNotFoundError as exc:
                raise exceptions.NotFound("Branch not found.") from exc
            except AddressNotFoundError as exc:
                raise exceptions.NotFound("Address not found.") from exc
            except BelowMinimumOrderAmountError as exc:
                raise exceptions.ValidationError(str(exc)) from exc
            return 201, OrderResponseSerializer(order).data

        return self.perform_idempotent(scope="orders.checkout", handler=handler)


class OrderListView(APIView):
    """calls OrderService.list_for_customer() -- see apps/orders/services/order_service.py."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version):
        customer_id = _customer_id_for(request)
        orders = OrderService().list_for_customer(customer_id)
        return Response(OrderResponseSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    """calls OrderService.get_owned() -- see apps/orders/services/order_service.py. An order
    id owned by a different customer returns 404, never 403 (same pattern as
    apps.cart.api.views.CartItemDetailView)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, version, pk):
        customer_id = _customer_id_for(request)
        try:
            order = OrderService().get_owned(customer_id=customer_id, order_id=pk)
        except OrderNotFoundError as exc:
            raise exceptions.NotFound("Order not found.") from exc
        return Response(OrderResponseSerializer(order).data)
