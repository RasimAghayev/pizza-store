from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class LoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class RefreshSerializer(StrictSerializer):
    """refresh_token is required only for non-browser clients (ADR 0006) -- browser clients
    send it as the httpOnly refresh cookie instead; see views.py's _read_refresh_token."""

    refresh_token = serializers.CharField(required=False, allow_blank=False)
