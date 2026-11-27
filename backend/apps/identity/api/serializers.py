from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class LoginSerializer(StrictSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)


class RefreshSerializer(StrictSerializer):
    """refresh_token is required only for non-browser clients (ADR 0006) -- browser clients
    send it as the httpOnly refresh cookie instead; see views.py's _read_refresh_token."""

    refresh_token = serializers.CharField(required=False, allow_blank=False)


class PasswordResetRequestSerializer(StrictSerializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(StrictSerializer):
    token = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class SocialLoginSerializer(StrictSerializer):
    """Shared across google/apple/facebook (Issue #178): Google/Apple only ever send
    id_token, Facebook sends either id_token (Limited Login) or access_token (classic OAuth2)
    -- see each provider's own verify_token() in django-allauth. Which field is actually
    required for a given provider is validated by that provider's verify_token() itself (it
    raises its own "invalid_token" error when the one it needs is missing), not duplicated
    here, so the requirement stays defined in exactly one place."""

    id_token = serializers.CharField(required=False, allow_blank=False, trim_whitespace=False)
    access_token = serializers.CharField(required=False, allow_blank=False, trim_whitespace=False)
