from rest_framework import serializers

from shared.api.serializers import StrictSerializer


class _ExampleSerializer(StrictSerializer):
    name = serializers.CharField()


def test_accepts_only_declared_fields():
    serializer = _ExampleSerializer(data={"name": "Mario"})

    assert serializer.is_valid()


def test_rejects_an_unknown_field():
    serializer = _ExampleSerializer(data={"name": "Mario", "is_admin": True})

    assert not serializer.is_valid()
    assert "is_admin" in serializer.errors
