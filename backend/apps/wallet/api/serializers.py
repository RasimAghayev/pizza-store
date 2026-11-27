from decimal import Decimal

from rest_framework import serializers

from apps.payments.domain.payment_method import PaymentMethod
from shared.api.serializers import StrictSerializer

# A customer cannot fund a top-up out of their own wallet -- only an external-funding method
# makes sense here (Issue #199 Architecture Requirements: top-up is "funded through Issue
# #198's existing gateways").
_TOPUP_PAYMENT_METHOD_CHOICES = [
    (method.value, method.value) for method in PaymentMethod if method != PaymentMethod.WALLET
]


class TopUpRequestSerializer(StrictSerializer):
    """Mirrors `apps.payments.api.serializers.PaymentCaptureRequestSerializer`'s
    `payment_method`/`payment_method_token` cross-field validation, minus `order_id` -- a
    top-up has no order to own."""

    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=_TOPUP_PAYMENT_METHOD_CHOICES)
    payment_method_token = serializers.CharField(required=False, allow_blank=False)

    # Field name, not a credential -- Bandit's B105 heuristic flags any dict key containing
    # "token" (same false positive already suppressed in apps/identity/api/views.py and
    # apps/payments/api/serializers.py).
    def validate(self, attrs):
        attrs = super().validate(attrs)
        token = attrs.get("payment_method_token")
        if attrs["payment_method"] == PaymentMethod.MOCK_ONLINE and not token:
            raise serializers.ValidationError(
                {
                    "payment_method_token": (  # nosec B105
                        "This field is required for mock_online payments."
                    )
                }
            )
        if attrs["payment_method"] == PaymentMethod.CASH_ON_DELIVERY and token:
            raise serializers.ValidationError(
                {
                    "payment_method_token": (  # nosec B105
                        "This field is not accepted for cash_on_delivery payments."
                    )
                }
            )
        return attrs


class WalletTransactionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    reference_type = serializers.CharField()
    reference_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()


class TopUpResponseSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class WalletBalanceResponseSerializer(serializers.Serializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    transactions = WalletTransactionSerializer(many=True)
