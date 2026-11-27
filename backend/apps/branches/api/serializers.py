from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class BranchCreateSerializer(StrictSerializer):
    restaurant_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=255)
    address = serializers.CharField(max_length=500)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    phone = serializers.CharField(max_length=32)
    delivery_radius_km = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    minimum_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    average_prep_time_minutes = serializers.IntegerField(min_value=0)
    capacity = serializers.IntegerField(min_value=0)
    is_active = serializers.BooleanField(required=False, default=True)


class BranchUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    address = serializers.CharField(max_length=500, required=False)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    phone = serializers.CharField(max_length=32, required=False)
    delivery_radius_km = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, required=False
    )
    delivery_fee = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    minimum_order_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, required=False
    )
    average_prep_time_minutes = serializers.IntegerField(min_value=0, required=False)
    capacity = serializers.IntegerField(min_value=0, required=False)
    is_active = serializers.BooleanField(required=False)


class BranchSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    restaurant_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    phone = serializers.CharField()
    delivery_radius_km = serializers.DecimalField(max_digits=5, decimal_places=2)
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_prep_time_minutes = serializers.IntegerField()
    capacity = serializers.IntegerField()
    is_active = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class BusinessHoursWriteSerializer(StrictSerializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    opens_at = serializers.TimeField()
    closes_at = serializers.TimeField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["opens_at"] >= attrs["closes_at"]:
            raise serializers.ValidationError(
                {"closes_at": "Must be later than opens_at (overnight hours are not supported)."}
            )
        return attrs


class BusinessHoursSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    weekday = serializers.IntegerField()
    opens_at = serializers.TimeField()
    closes_at = serializers.TimeField()


class BranchClosureCreateSerializer(StrictSerializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["starts_at"] >= attrs["ends_at"]:
            raise serializers.ValidationError({"ends_at": "Must be later than starts_at."})
        return attrs


class BranchClosureSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    reason = serializers.CharField()
