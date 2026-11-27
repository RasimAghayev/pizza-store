from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class CustomerRegistrationSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class ProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(allow_blank=True)
    last_name = serializers.CharField(allow_blank=True)
    phone = serializers.CharField(allow_null=True)
    date_of_birth = serializers.DateField(allow_null=True)
    consent_personal_data_at = serializers.DateTimeField(allow_null=True)


class ProfileUpdateSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=32, allow_blank=True, allow_null=True, required=False)
    date_of_birth = serializers.DateField(allow_null=True, required=False)


class AddressSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField(allow_blank=True)
    street_and_unit = serializers.CharField()
    city = serializers.CharField()
    postal_code = serializers.CharField(allow_blank=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()


class AddressCreateSerializer(StrictSerializer):
    label = serializers.CharField(max_length=50, allow_blank=True, required=False, default="")
    street_and_unit = serializers.CharField()
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20, allow_blank=True, required=False, default="")
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, default=None
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True, default=None
    )
    is_default = serializers.BooleanField(required=False, default=False)


class AddressUpdateSerializer(StrictSerializer):
    label = serializers.CharField(max_length=50, allow_blank=True, required=False)
    street_and_unit = serializers.CharField(required=False)
    city = serializers.CharField(max_length=100, required=False)
    postal_code = serializers.CharField(max_length=20, allow_blank=True, required=False)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    is_default = serializers.BooleanField(required=False)
