from rest_framework import serializers

from apps.products.models import OptionGroupKind
from shared.api.serializers import StrictSerializer


class ProductCreateSerializer(StrictSerializer):
    organization_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    is_active = serializers.BooleanField(required=False, default=True)
    allergen_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )


class ProductUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    base_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    is_active = serializers.BooleanField(required=False)
    allergen_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )


class ProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class OptionGroupCreateSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=OptionGroupKind.choices)
    is_required = serializers.BooleanField(required=False, default=True)
    allows_multiple = serializers.BooleanField(required=False, default=False)


class OptionGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    kind = serializers.CharField()
    is_required = serializers.BooleanField()
    allows_multiple = serializers.BooleanField()


class OptionChoiceCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255)
    price_delta = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0
    )


class OptionChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    option_group_id = serializers.IntegerField()
    name = serializers.CharField()
    price_delta = serializers.DecimalField(max_digits=10, decimal_places=2)


class ToppingCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255)
    price_delta = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, default=0
    )
    sku_reference = serializers.CharField(
        max_length=64, required=False, allow_null=True, default=None
    )
    allergen_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )


class ToppingUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    price_delta = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    sku_reference = serializers.CharField(max_length=64, required=False, allow_null=True)
    allergen_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False
    )


class ToppingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    price_delta = serializers.DecimalField(max_digits=10, decimal_places=2)
    sku_reference = serializers.CharField(allow_null=True)


class ProductToppingAttachSerializer(StrictSerializer):
    topping_id = serializers.IntegerField(min_value=1)
    is_default_included = serializers.BooleanField(required=False, default=False)


class ProductToppingSerializer(serializers.Serializer):
    topping_id = serializers.IntegerField()
    name = serializers.CharField(source="topping.name")
    price_delta = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="topping.price_delta"
    )
    is_default_included = serializers.BooleanField()


class AllergenCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255)


class AllergenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class HalfAndHalfOtherHalfSerializer(StrictSerializer):
    product_id = serializers.IntegerField(min_value=1)
    option_choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    topping_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )


class PriceQuoteRequestSerializer(StrictSerializer):
    """The URL's `<id>` (Issue #181: `POST /api/v1/products/<id>/price-quote/`) is always
    the first/primary product; `option_choice_ids`/`topping_ids` describe its own build.
    For a half-and-half quote, `other_half` supplies the second product's id and its own
    selection -- see domain/pricing.py's documented averaging rule."""

    option_choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    topping_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    other_half = HalfAndHalfOtherHalfSerializer(required=False)
    quantity = serializers.IntegerField(min_value=1, required=False, default=1)


class PriceQuoteResponseSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
