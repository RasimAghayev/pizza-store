from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class OrganizationCreateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255)
    owner_user_id = serializers.IntegerField(min_value=1)


class OrganizationUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)


class OrganizationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    owner_user_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class RestaurantCreateSerializer(StrictSerializer):
    organization_id = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class RestaurantUpdateSerializer(StrictSerializer):
    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)


class RestaurantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization_id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    created_at = serializers.DateTimeField()
