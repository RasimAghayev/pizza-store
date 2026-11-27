import uuid
from dataclasses import asdict

from django.db import transaction

# calls apps.orders.services.order_service.OrderService.get_owned()/.transition() -- see
# backend/apps/orders/README.md. orders never imports apps.payments.models/repositories
# directly (ADR 0004); payment capture reads/mutates Order state only through this service
# entry point. OrderStatus itself is a pure, Django-free domain enum
# (apps.orders.domain.state_machine) -- cross-module domain-enum imports are already
# precedented by apps.customers.services.verification_service importing
# apps.identity.domain.rbac.RoleCode.
from apps.orders.domain.state_machine import OrderStatus
from apps.orders.services.order_service import OrderService
from apps.payments.domain.gateway_registry import get_gateway
from apps.payments.domain.payment_status import PaymentStatus
from apps.payments.events.payment_completed import EVENT_TYPE as PAYMENT_COMPLETED_EVENT_TYPE
from apps.payments.events.payment_completed import (
    SCHEMA_VERSION as PAYMENT_COMPLETED_SCHEMA_VERSION,
)
from apps.payments.events.payment_completed import PaymentCompletedPayload
from apps.payments.events.payment_failed import EVENT_TYPE as PAYMENT_FAILED_EVENT_TYPE
from apps.payments.events.payment_failed import SCHEMA_VERSION as PAYMENT_FAILED_SCHEMA_VERSION
from apps.payments.events.payment_failed import PaymentFailedPayload
from apps.payments.models.payment import Payment
from apps.payments.models.payment_outbox_event import PaymentOutboxEvent
from apps.payments.repositories.payment_repository import PaymentRepository

# This platform has no multi-currency requirement anywhere else in the codebase (Order/Branch/
# Product all store a bare Decimal with no currency field) -- fixed to a single implicit
# currency for this Task, same "decide the ambiguous bit, document it" pattern as Issue #196's
# branch-switch decision. Revisit if a real multi-currency requirement appears later.
DEFAULT_CURRENCY = "USD"

__all__ = ["PaymentService", "OrderNotPendingPaymentError", "DEFAULT_CURRENCY"]


class OrderNotPendingPaymentError(Exception):
    """Raised when a capture is attempted against an Order that isn't (or is no longer)
    `OrderStatus.PENDING_PAYMENT` -- e.g. already paid, cancelled, or mid-fulfillment. Checked
    here, inside `capture_for_order()`, which `PaymentCaptureView` only ever calls from inside
    the handler closure it passes to `perform_idempotent()` -- never before it is called: a
    duplicate capture request carrying the same `Idempotency-Key` must replay the first
    request's cached response, not re-run this check against the order's now-`CONFIRMED`
    post-capture state (same lesson Issue #197's checkout-replay bug taught; see
    apps/orders/api/views.py::CheckoutView and the project memory on idempotent-handler
    side-effect ordering)."""


class PaymentService:
    def __init__(
        self,
        *,
        repository: PaymentRepository | None = None,
        order_service: OrderService | None = None,
    ) -> None:
        self._payments = repository or PaymentRepository()
        self._orders = order_service or OrderService()

    def capture_for_order(
        self,
        *,
        order_id: int,
        customer_id: int,
        payment_method: str,
        payment_method_token: str | None,
        idempotency_key: str,
    ) -> Payment:
        """Converts an Order in `PENDING_PAYMENT` into `CONFIRMED` (gateway success) or
        `PAYMENT_FAILED` (gateway failure) (Issue #198). Looks up the gateway via the registry
        keyed by `payment_method`, authorizes then immediately captures the full order total
        in one call (no partial-capture use case exists in this Task). The gateway calls
        happen before the DB transaction opens -- they represent (simulated) external effects
        that a DB rollback could never undo, so only the local `Payment` row write and the
        `Order` transition are wrapped atomically."""
        order = self._orders.get_owned(customer_id=customer_id, order_id=order_id)
        if OrderStatus(order.status) != OrderStatus.PENDING_PAYMENT:
            raise OrderNotPendingPaymentError(order_id)

        gateway = get_gateway(payment_method)
        amount = order.total_amount

        authorization = gateway.authorize(
            amount=amount,
            currency=DEFAULT_CURRENCY,
            payment_method_token=payment_method_token,
            idempotency_key=idempotency_key,
            customer_id=customer_id,
        )
        capture = (
            gateway.capture(authorization_id=authorization.authorization_id, amount=amount)
            if authorization.success
            else None
        )
        succeeded = authorization.success and capture is not None and capture.success
        if capture is not None:
            provider_reference = capture.provider_reference
            failure_reason = capture.failure_reason
        else:
            provider_reference = authorization.provider_reference
            failure_reason = authorization.failure_reason

        with transaction.atomic():
            payment = self._payments.create_payment(
                order_id=order_id,
                gateway=payment_method,
                amount=amount,
                currency=DEFAULT_CURRENCY,
                status=PaymentStatus.CAPTURED if succeeded else PaymentStatus.FAILED,
                provider_reference=provider_reference,
                idempotency_key=idempotency_key,
            )
            if succeeded:
                self._orders.transition(
                    order_id=order_id, to_status=OrderStatus.CONFIRMED, reason=None
                )
                self._publish_payment_completed(payment)
            else:
                self._orders.transition(
                    order_id=order_id,
                    to_status=OrderStatus.PAYMENT_FAILED,
                    reason=failure_reason,
                )
                self._publish_payment_failed(payment, reason=failure_reason)

        return payment

    def _publish_payment_completed(self, payment: Payment) -> None:
        payload = PaymentCompletedPayload(
            payment_id=payment.pk,
            order_id=payment.order_id,
            amount=str(payment.amount),
            currency=payment.currency,
        )
        PaymentOutboxEvent.objects.create(
            aggregate_type="payment",
            aggregate_id=str(payment.pk),
            event_type=PAYMENT_COMPLETED_EVENT_TYPE,
            schema_version=PAYMENT_COMPLETED_SCHEMA_VERSION,
            payload=asdict(payload),
            correlation_id=uuid.uuid4(),
        )

    def _publish_payment_failed(self, payment: Payment, *, reason: str | None) -> None:
        payload = PaymentFailedPayload(
            payment_id=payment.pk, order_id=payment.order_id, reason=reason
        )
        PaymentOutboxEvent.objects.create(
            aggregate_type="payment",
            aggregate_id=str(payment.pk),
            event_type=PAYMENT_FAILED_EVENT_TYPE,
            schema_version=PAYMENT_FAILED_SCHEMA_VERSION,
            payload=asdict(payload),
            correlation_id=uuid.uuid4(),
        )
