from django.db import models


class HealthPing(models.Model):
    """Exists purely to give Task #108/#110 a real migration to exercise end-to-end."""

    note = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
