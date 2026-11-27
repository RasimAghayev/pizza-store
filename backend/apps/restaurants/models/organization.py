from django.db import models


class Organization(models.Model):
    """ADR 0006's top-level multi-tenant boundary (Issue #180's gap-fill: modeled here in
    `restaurants` since no app named `organizations` exists -- see this module's README).
    `owner_user_id` is a plain field, not a cross-app FK to `identity.User`, same pattern as
    `identity.RoleAssignment` (ADR 0004 forbids this app importing `identity.models`)."""

    name = models.CharField(max_length=255)
    owner_user_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "restaurants"

    def __str__(self) -> str:
        return self.name
