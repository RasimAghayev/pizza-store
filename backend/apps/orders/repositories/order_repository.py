from decimal import Decimal

from apps.orders.domain.state_machine import OrderStatus
from apps.orders.models.order import Order
from apps.orders.models.order_item import OrderItem
from apps.orders.models.order_status_audit import OrderStatusAudit


class OrderRepository:
    """Only file in this module allowed to issue an ORM query for Order/OrderItem/
    OrderStatusAudit, per ADR 0004."""

    def create_order(
        self,
        *,
        customer_id: int,
        branch_id: int,
        status: OrderStatus,
        subtotal: Decimal,
        delivery_fee: Decimal,
        discount_amount: Decimal,
        total_amount: Decimal,
        delivery_street_and_unit: str,
        delivery_city: str,
        delivery_postal_code: str,
        delivery_latitude: Decimal | None,
        delivery_longitude: Decimal | None,
        idempotency_key: str,
    ) -> Order:
        return Order.objects.create(
            customer_id=customer_id,
            branch_id=branch_id,
            status=status.value,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount_amount=discount_amount,
            total_amount=total_amount,
            delivery_street_and_unit=delivery_street_and_unit,
            delivery_city=delivery_city,
            delivery_postal_code=delivery_postal_code,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            idempotency_key=idempotency_key,
        )

    def create_items(self, order_id: int, items: list[dict]) -> list[OrderItem]:
        return list(
            OrderItem.objects.bulk_create([OrderItem(order_id=order_id, **item) for item in items])
        )

    def create_audit(
        self,
        *,
        order_id: int,
        from_status: OrderStatus | None,
        to_status: OrderStatus,
        reason: str | None,
    ) -> OrderStatusAudit:
        return OrderStatusAudit.objects.create(
            order_id=order_id,
            from_status=from_status.value if from_status is not None else None,
            to_status=to_status.value,
            reason=reason,
        )

    def get_by_id(self, order_id: int) -> Order | None:
        return Order.objects.filter(pk=order_id).prefetch_related("items").first()

    def get_for_customer(self, order_id: int, customer_id: int) -> Order | None:
        return (
            Order.objects.filter(pk=order_id, customer_id=customer_id)
            .prefetch_related("items")
            .first()
        )

    def list_for_customer(self, customer_id: int) -> list[Order]:
        return list(Order.objects.filter(customer_id=customer_id).prefetch_related("items"))

    def update_status(self, order: Order, status: OrderStatus) -> Order:
        order.status = status.value
        order.save(update_fields=["status"])
        return order
