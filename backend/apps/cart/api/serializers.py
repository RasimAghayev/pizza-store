from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class CartHalfSerializer(StrictSerializer):
    """One half of a half-and-half build -- same shape as
    `apps.products.api.serializers.HalfAndHalfOtherHalfSerializer`, duplicated locally
    rather than imported (ADR 0004: `cart` never imports `apps.products.api`, only its
    `services/` entry point)."""

    product_id = serializers.IntegerField(min_value=1)
    option_choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    topping_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )


class CartHalfAndHalfSerializer(StrictSerializer):
    first = CartHalfSerializer()
    second = CartHalfSerializer()


class CartItemCreateSerializer(StrictSerializer):
    """Exactly one of `product_id` (a single-build item) or `half_and_half` (two independent
    halves, see `apps/products/domain/pricing.py`'s averaging rule) must be provided --
    enforced in `validate()` below, mirroring `PricingService.quote()`'s own either/or
    contract."""

    branch_id = serializers.IntegerField(min_value=1)
    product_id = serializers.IntegerField(min_value=1, required=False)
    option_choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    topping_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    half_and_half = CartHalfAndHalfSerializer(required=False)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        has_product = attrs.get("product_id") is not None
        has_half_and_half = attrs.get("half_and_half") is not None
        if has_product == has_half_and_half:
            raise serializers.ValidationError("Provide exactly one of product_id or half_and_half.")
        return attrs


class CartItemQuantityUpdateSerializer(StrictSerializer):
    quantity = serializers.IntegerField(min_value=1)


class CartItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField(allow_null=True)
    option_choice_ids = serializers.ListField(child=serializers.IntegerField())
    topping_ids = serializers.ListField(child=serializers.IntegerField())
    half_and_half = serializers.JSONField(allow_null=True)
    quantity = serializers.IntegerField()
    note = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2)


class CartResponseSerializer(serializers.Serializer):
    """`id`/`branch_id` are nullable: a customer who has never added an item gets this
    shape with both null and `items: []` rather than a 404 (Issue #196's cart is a singleton
    resource from the client's point of view -- see
    `apps/cart/services/cart_service.py::CartService.get_priced_active_cart`)."""

    id = serializers.IntegerField(allow_null=True)
    branch_id = serializers.IntegerField(allow_null=True)
    items = CartItemResponseSerializer(many=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
