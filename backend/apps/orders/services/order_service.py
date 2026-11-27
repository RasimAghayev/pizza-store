import uuid
from dataclasses import asdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

# calls apps.branches.services.branch_service.BranchService.get_by_id() -- see
# backend/apps/branches/README.md. orders never imports apps.branches.models/repositories
# directly (ADR 0004); the live Branch row (for delivery_fee/minimum_order_amount) is only
# ever read through this service entry point. Order.branch itself is a real lazy-string FK,
# unrelated to this read.
from apps.branches.services.branch_service import BranchService

# calls apps.cart.services.cart_service.CartService -- see backend/apps/cart/README.md.
# orders never imports apps.cart.models/repositories directly (ADR 0004); checkout reuses
# CartService.price_cart() to re-price every line (Issue #197 Technical Context) rather than
# duplicating PricingService logic, and CartService.clear() to empty the cart afterward.
from apps.cart.services.cart_service import CartService, PricedCartItem

# calls apps.customers.services.address_service.AddressService.get_owned_by_customer_id() --
# see backend/apps/customers/README.md. orders never imports apps.customers.models/
# repositories directly (ADR 0004); Order's delivery_* fields are a one-time snapshot of the
# resolved Address, never a live FK.
from apps.customers.services.address_service import AddressService
from apps.orders.domain.state_machine import OrderStatus, next_status
from apps.orders.events.order_confirmed import EVENT_TYPE as ORDER_CONFIRMED_EVENT_TYPE
from apps.orders.events.order_confirmed import SCHEMA_VERSION as ORDER_CONFIRMED_SCHEMA_VERSION
from apps.orders.events.order_confirmed import OrderConfirmedPayload
from apps.orders.events.order_created import EVENT_TYPE as ORDER_CREATED_EVENT_TYPE
from apps.orders.events.order_created import SCHEMA_VERSION as ORDER_CREATED_SCHEMA_VERSION
from apps.orders.events.order_created import OrderCreatedPayload
from apps.orders.models.order import Order
from apps.orders.models.order_outbox_event import OrderOutboxEvent
from apps.orders.repositories.order_repository import OrderRepository

# calls apps.products.services.product_service.ProductService.get_by_id() -- see
# backend/apps/products/README.md. orders never imports apps.products.models/repositories
# directly (ADR 0004); OrderItem.name/selection are a one-time snapshot taken at checkout.
from apps.products.services.product_service import ProductService

__all__ = [
    "OrderService",
    "CartNotFoundError",
    "BranchNotFoundError",
    "AddressNotFoundError",
    "BelowMinimumOrderAmountError",
    "OrderNotFoundError",
    "ProductNotFoundError",
]


class CartNotFoundError(Exception):
    """Raised when the customer has no active cart, or the referenced `cart_id` no longer
    matches it -- checkout always re-resolves the cart server-side (Issue #197 Security
    Requirements), so a client never supplies a cart id beyond what its own active cart
    already resolved."""


class BranchNotFoundError(Exception):
    pass


class AddressNotFoundError(Exception):
    """Raised for an address id that doesn't exist, or exists but isn't owned by this
    customer -- same 404-not-403 semantics as
    `apps.customers.services.address_service.AddressNotFoundError`, re-declared locally since
    orders never imports that module's exception types (ADR 0004)."""


class BelowMinimumOrderAmountError(Exception):
    pass


class OrderNotFoundError(Exception):
    pass


class ProductNotFoundError(Exception):
    """A cart line's product disappeared between `CartService.price_cart()`'s quote call and
    this snapshot read -- both happen inside the same request, so this is not expected in
    practice, but `ProductService.get_by_id()` is `Product | None` and must be checked."""


class OrderService:
    def __init__(
        self,
        *,
        repository: OrderRepository | None = None,
        cart_service: CartService | None = None,
        branch_service: BranchService | None = None,
        address_service: AddressService | None = None,
        product_service: ProductService | None = None,
    ) -> None:
        self._orders = repository or OrderRepository()
        self._cart_service = cart_service or CartService()
        self._branch_service = branch_service or BranchService()
        self._address_service = address_service or AddressService()
        self._product_service = product_service or ProductService()

    def checkout(
        self, *, customer_id: int, cart_id: int, address_id: int, idempotency_key: str
    ) -> Order:
        """Converts the customer's own active cart into an `Order` in `PENDING_PAYMENT`
        (Issue #197). `cart_id` is re-validated against the customer's own active cart rather
        than trusted on its own (Security Requirements); every price is a fresh
        `PricingService.quote()` call by way of `CartService.price_cart()`, never the cart's
        stored `unit_price_snapshot`. Duplicate-submission protection itself lives one layer
        up, in the DRF view's mandatory `Idempotency-Key` + `IdempotentActionMixin` (Issue
        #195) -- `idempotency_key` here is recorded on the `Order` row for traceability only."""
        cart = self._cart_service.get_active_cart(customer_id)
        if cart is None or cart.pk != cart_id:
            raise CartNotFoundError(cart_id)

        priced = self._cart_service.price_cart(cart)
        if not priced.items:
            raise CartNotFoundError(cart_id)

        branch = self._branch_service.get_by_id(cart.branch_id)
        if branch is None:
            raise BranchNotFoundError(cart.branch_id)

        if priced.total < branch.minimum_order_amount:
            raise BelowMinimumOrderAmountError(
                f"Order subtotal {priced.total} is below branch {branch.pk}'s minimum of "
                f"{branch.minimum_order_amount}."
            )

        address = self._address_service.get_owned_by_customer_id(
            customer_id=customer_id, address_id=address_id
        )
        if address is None:
            raise AddressNotFoundError(address_id)

        total_amount = priced.total + branch.delivery_fee

        with transaction.atomic():
            order = self._orders.create_order(
                customer_id=customer_id,
                branch_id=branch.pk,
                status=OrderStatus.PENDING_PAYMENT,
                subtotal=priced.total,
                delivery_fee=branch.delivery_fee,
                discount_amount=Decimal("0.00"),
                total_amount=total_amount,
                delivery_street_and_unit=address.street_and_unit,
                delivery_city=address.city,
                delivery_postal_code=address.postal_code,
                delivery_latitude=address.latitude,
                delivery_longitude=address.longitude,
                idempotency_key=idempotency_key,
            )
            self._orders.create_items(
                order.pk, [self._snapshot_item(item) for item in priced.items]
            )
            self._orders.create_audit(
                order_id=order.pk,
                from_status=None,
                to_status=OrderStatus.PENDING_PAYMENT,
                reason=None,
            )
            self._cart_service.clear(customer_id)
            self._publish_order_created(order)

        return order

    def transition(
        self, *, order_id: int, to_status: OrderStatus, reason: str | None = None
    ) -> Order:
        """The generic status-change entry point (Issue #197) -- not reachable through any
        Phase 11 endpoint; Task #198 (payment) and later Phase 12 modules call this directly.
        Every call inserts exactly one `OrderStatusAudit` row in the same transaction as the
        status change, checked against `state_machine.TRANSITIONS`."""
        order = self._orders.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)

        current = OrderStatus(order.status)
        new_status = next_status(current=current, target=to_status)

        with transaction.atomic():
            order = self._orders.update_status(order, new_status)
            self._orders.create_audit(
                order_id=order.pk, from_status=current, to_status=new_status, reason=reason
            )
            if new_status == OrderStatus.CONFIRMED:
                self._publish_order_confirmed(order)

        return order

    def get_owned(self, *, customer_id: int, order_id: int) -> Order:
        order = self._orders.get_for_customer(order_id, customer_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    def list_for_customer(self, customer_id: int) -> list[Order]:
        return self._orders.list_for_customer(customer_id)

    def _snapshot_item(self, item: PricedCartItem) -> dict:
        if item.half_and_half is not None:
            first_id = item.half_and_half["first"]["product_id"]
            second_id = item.half_and_half["second"]["product_id"]
            first = self._product_service.get_by_id(first_id)
            second = self._product_service.get_by_id(second_id)
            if first is None:
                raise ProductNotFoundError(first_id)
            if second is None:
                raise ProductNotFoundError(second_id)
            name = f"{first.name} / {second.name} (Half & Half)"
            selection: dict = {"half_and_half": item.half_and_half}
        elif item.product_id is not None:
            product = self._product_service.get_by_id(item.product_id)
            if product is None:
                raise ProductNotFoundError(item.product_id)
            name = product.name
            selection = {
                "product_id": item.product_id,
                "option_choice_ids": item.option_choice_ids,
                "topping_ids": item.topping_ids,
            }
        else:
            raise ProductNotFoundError(item.product_id)
        return {
            "product_id": item.product_id,
            "name": name,
            "selection": selection,
            "unit_price": item.unit_price,
            "quantity": item.quantity,
            "line_total": item.line_total,
        }

    def _publish_order_created(self, order: Order) -> None:
        payload = OrderCreatedPayload(
            order_id=order.pk,
            customer_id=order.customer_id,
            branch_id=order.branch_id,
            total_amount=str(order.total_amount),
            created_at=order.created_at.isoformat(),
        )
        OrderOutboxEvent.objects.create(
            aggregate_type="order",
            aggregate_id=str(order.pk),
            event_type=ORDER_CREATED_EVENT_TYPE,
            schema_version=ORDER_CREATED_SCHEMA_VERSION,
            payload=asdict(payload),
            correlation_id=uuid.uuid4(),
        )

    def _publish_order_confirmed(self, order: Order) -> None:
        payload = OrderConfirmedPayload(
            order_id=order.pk,
            customer_id=order.customer_id,
            confirmed_at=timezone.now().isoformat(),
        )
        OrderOutboxEvent.objects.create(
            aggregate_type="order",
            aggregate_id=str(order.pk),
            event_type=ORDER_CONFIRMED_EVENT_TYPE,
            schema_version=ORDER_CONFIRMED_SCHEMA_VERSION,
            payload=asdict(payload),
            correlation_id=uuid.uuid4(),
        )
