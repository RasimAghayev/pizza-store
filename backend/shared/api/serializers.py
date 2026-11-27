from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    """Base for every module's input serializer (ADR 0006: "unknown/unexpected fields are
    rejected, not silently ignored"). A plain `serializers.Serializer` otherwise drops any
    key in `initial_data` that isn't a declared field instead of rejecting it.

    `getattr(self, "initial_data", None)`, not a direct attribute access: when a
    StrictSerializer subclass is nested as a field inside another serializer (e.g. a
    half-and-half selection field), DRF's own field-validation path never constructs that
    nested instance with a `data=` kwarg (only a top-level `Serializer(data=...)` call sets
    `initial_data` -- see rest_framework.serializers.BaseSerializer.__init__), so
    `self.initial_data` is simply absent on it; a bare attribute access would raise
    AttributeError instead of validating normally."""

    def validate(self, attrs):
        initial_data = getattr(self, "initial_data", None)
        if isinstance(initial_data, dict):
            unknown = set(initial_data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: "Unknown field." for field in sorted(unknown)}
                )
        return attrs
