from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class CheckoutRequestSerializer(StrictSerializer):
    """Accepts only `address_id` -- no amount/total field exists at all, so there is nothing
    for the server to even compare a client-sent value against (Issue #197 Architecture
    Requirements: checkout recalculates `subtotal`/`delivery_fee`/`total_amount` entirely
    server-side). `cart_id` is resolved server-side from the authenticated customer's own
    active cart, never accepted here (Security Requirements)."""

    address_id = serializers.IntegerField(min_value=1)


class OrderItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    selection = serializers.JSONField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    delivery_street_and_unit = serializers.CharField()
    delivery_city = serializers.CharField()
    delivery_postal_code = serializers.CharField(allow_blank=True)
    delivery_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    delivery_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    created_at = serializers.DateTimeField()
    items = OrderItemResponseSerializer(many=True)
