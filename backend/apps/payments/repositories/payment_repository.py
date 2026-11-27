from decimal import Decimal

from apps.payments.domain.payment_status import PaymentStatus
from apps.payments.models.payment import Payment


class PaymentRepository:
    """Only file in this module allowed to issue an ORM query for Payment, per ADR 0004."""

    def create_payment(
        self,
        *,
        order_id: int,
        gateway: str,
        amount: Decimal,
        currency: str,
        status: PaymentStatus,
        provider_reference: str,
        idempotency_key: str,
    ) -> Payment:
        return Payment.objects.create(
            order_id=order_id,
            gateway=gateway,
            amount=amount,
            currency=currency,
            status=status.value,
            provider_reference=provider_reference,
            idempotency_key=idempotency_key,
        )

    def get_by_id(self, payment_id: int) -> Payment | None:
        return Payment.objects.filter(pk=payment_id).first()

    def list_for_order(self, order_id: int) -> list[Payment]:
        return list(Payment.objects.filter(order_id=order_id))
