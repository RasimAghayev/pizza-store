from rest_framework import serializers

from apps.payments.domain.payment_method import PaymentMethod
from shared.api.serializers import StrictSerializer

_PAYMENT_METHOD_CHOICES = [(method.value, method.value) for method in PaymentMethod]


class PaymentCaptureRequestSerializer(StrictSerializer):
    """`payment_method_token` is required for `mock_online` and rejected for
    `cash_on_delivery` (Issue #198 Architecture Requirements -- "no extra field for
    cash_on_delivery") -- cross-field enforcement happens in `validate()` since a DRF field's
    own `required=` can't depend on a sibling field's value. `order_id` ownership is checked
    by the view, never here."""

    order_id = serializers.IntegerField(min_value=1)
    payment_method = serializers.ChoiceField(choices=_PAYMENT_METHOD_CHOICES)
    payment_method_token = serializers.CharField(required=False, allow_blank=False)

    # Field name, not a credential -- Bandit's B105 heuristic flags any dict key containing
    # "token" (same false positive already suppressed in apps/identity/api/views.py).
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


class PaymentResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    order_id = serializers.IntegerField()
    gateway = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    provider_reference = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
