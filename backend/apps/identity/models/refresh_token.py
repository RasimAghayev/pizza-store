from django.conf import settings
from django.db import models


class RefreshToken(models.Model):
    """Opaque refresh token, ADR 0006 -- only its SHA-256 hash is ever persisted; the raw
    value lives only in the httpOnly cookie/response body handed to the client."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="refresh_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaces"
    )
    device_label = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Snapshot of the access-token claims this refresh token's family was issued with (Issue
    # #175) -- rotation carries these forward unchanged rather than re-querying
    # role_assignments on every refresh; a role change only takes effect on the next full
    # login (see apps/identity/README.md for this deliberate limitation).
    roles_snapshot = models.JSONField(default=list, blank=True)
    organization_id = models.PositiveBigIntegerField(null=True, blank=True)
    branch_id = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        app_label = "identity"
