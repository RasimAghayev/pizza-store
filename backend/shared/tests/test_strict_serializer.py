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


class _ParentSerializer(StrictSerializer):
    nested = _ExampleSerializer()


def test_nested_as_a_field_does_not_raise_even_though_it_has_no_initial_data():
    """A StrictSerializer nested as a field of another serializer is never constructed
    with a `data=` kwarg by DRF's own field-validation path, so it never gets an
    `initial_data` attribute -- this must degrade gracefully, not raise AttributeError."""
    serializer = _ParentSerializer(data={"nested": {"name": "Mario"}})

    assert serializer.is_valid(), serializer.errors
