from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    """Base for every module's input serializer (ADR 0006: "unknown/unexpected fields are
    rejected, not silently ignored"). A plain `serializers.Serializer` otherwise drops any
    key in `initial_data` that isn't a declared field instead of rejecting it."""

    def validate(self, attrs):
        if isinstance(self.initial_data, dict):
            unknown = set(self.initial_data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError(
                    {field: "Unknown field." for field in sorted(unknown)}
                )
        return attrs
