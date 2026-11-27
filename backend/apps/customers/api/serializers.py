from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class CustomerRegistrationSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
