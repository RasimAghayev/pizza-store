from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

# calls apps.customers.services.profile_service.ProfileService.get_profile() -- see
# backend/apps/customers/README.md. Same pattern as apps.orders.api.views._customer_id_for.
from apps.customers.services.profile_service import CustomerNotFoundError as ProfileNotFoundError
from apps.customers.services.profile_service import ProfileService

# calls apps.orders.services.order_service.OrderService.get_owned() -- see
# backend/apps/orders/README.md. Resolves order ownership before any capture is attempted
# (Security Requirements). Only ownership/existence is checked here -- the order's *status*
# is checked inside PaymentService.capture_for_order() itself, never in this pre-check, so a
# duplicate-key replay never re-evaluates the post-capture order state (see
# OrderNotPendingPaymentError's docstring in services/payment_service.py).
from apps.orders.services.order_service import OrderNotFoundError, OrderService
from apps.payments.api.serializers import PaymentCaptureRequestSerializer, PaymentResponseSerializer
from apps.payments.domain.gateway_registry import UnknownPaymentMethodError
from apps.payments.services.payment_service import OrderNotPendingPaymentError, PaymentService
from shared.idempotency.drf import IdempotentActionMixin


def _customer_id_for(request) -> int:
    try:
        return ProfileService().get_profile(request.user.pk).pk
    except ProfileNotFoundError as exc:
        raise exceptions.NotFound("Customer profile not found.") from exc


class PaymentCaptureView(IdempotentActionMixin, APIView):
    """calls PaymentService.capture_for_order() -- see
    apps/payments/services/payment_service.py. The `Idempotency-Key` header is mandatory
    here, same reasoning and same pattern as apps.orders.api.views.CheckoutView (Issue #198
    Test Requirements: a duplicate capture request must never double-charge or
    double-transition the order)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, version):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            raise exceptions.ValidationError(
                {"Idempotency-Key": "This header is required for payment capture."}
            )

        customer_id = _customer_id_for(request)
        serializer = PaymentCaptureRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]
        payment_method = serializer.validated_data["payment_method"]
        payment_method_token = serializer.validated_data.get("payment_method_token")

        try:
            OrderService().get_owned(customer_id=customer_id, order_id=order_id)
        except OrderNotFoundError as exc:
            raise exceptions.NotFound("Order not found.") from exc

        def handler() -> tuple[int, object]:
            try:
                payment = PaymentService().capture_for_order(
                    order_id=order_id,
                    customer_id=customer_id,
                    payment_method=payment_method,
                    payment_method_token=payment_method_token,
                    idempotency_key=idempotency_key,
                )
            except OrderNotPendingPaymentError as exc:
                raise exceptions.ValidationError("This order is not awaiting payment.") from exc
            except UnknownPaymentMethodError as exc:
                raise exceptions.ValidationError("Unknown payment method.") from exc
            return 201, PaymentResponseSerializer(payment).data

        return self.perform_idempotent(scope="payments.capture", handler=handler)
