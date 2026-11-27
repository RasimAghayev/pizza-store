from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class MenuCategoryCreateSerializer(StrictSerializer):
    organization_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=255)
    display_order = serializers.IntegerField(required=False, default=0)


class MenuCategoryUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    display_order = serializers.IntegerField(required=False)


class MenuCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    name = serializers.CharField()
    display_order = serializers.IntegerField()


class MenuItemCreateSerializer(StrictSerializer):
    branch_id = serializers.IntegerField(min_value=1)
    product_id = serializers.IntegerField(min_value=1)
    category_id = serializers.IntegerField(min_value=1)
    is_available = serializers.BooleanField(required=False, default=True)
    available_from = serializers.TimeField(required=False, allow_null=True, default=None)
    available_until = serializers.TimeField(required=False, allow_null=True, default=None)
    display_order = serializers.IntegerField(required=False, default=0)


class MenuItemUpdateSerializer(StrictSerializer):
    """`branch_id`/`product_id` are intentionally absent -- moving a menu item to a
    different branch/product is a delete-and-recreate, not a PATCH, same convention as
    `ProductUpdateSerializer` never accepting `organization_id` (Issue #181)."""

    category_id = serializers.IntegerField(min_value=1, required=False)
    is_available = serializers.BooleanField(required=False)
    available_from = serializers.TimeField(required=False, allow_null=True)
    available_until = serializers.TimeField(required=False, allow_null=True)
    display_order = serializers.IntegerField(required=False)


class MenuItemSerializer(serializers.Serializer):
    """Staff-facing shape (full CRUD views) -- ids only, no nested product/category data."""

    id = serializers.IntegerField()
    branch_id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    category_id = serializers.IntegerField()
    is_available = serializers.BooleanField()
    available_from = serializers.TimeField(allow_null=True)
    available_until = serializers.TimeField(allow_null=True)
    display_order = serializers.IntegerField()


class BranchMenuEntrySerializer(serializers.Serializer):
    """The public, customer-facing shape (`GET /api/v1/branches/<branch_id>/menu/`) --
    flattens the product's own name/price onto the entry via dotted `source=` lookups
    (same pattern as `ProductToppingSerializer`, Issue #181) so a customer-facing client
    doesn't need a second round-trip per item. Every entry returned by this serializer is
    already filtered to "available right now" by `MenuService.menu_for_branch`, so
    `is_available`/`available_from`/`available_until` are deliberately omitted -- a
    currently-visible item has nothing further to say about its own scheduling."""

    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    product_name = serializers.CharField(source="product.name")
    product_base_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, source="product.base_price"
    )
    category_id = serializers.IntegerField()
    display_order = serializers.IntegerField()
