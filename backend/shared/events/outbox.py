import uuid

from django.db import models


class OutboxEventStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PUBLISHED = "published", "Published"
    FAILED = "failed", "Failed"


class AbstractOutboxEvent(models.Model):
    """Transactional Outbox base table (ADR 0005) -- each publishing module subclasses this
    for its own concrete `outbox_events` table, inserting a row in the same DB transaction as
    its business rows. Relayed to RabbitMQ by shared/events/relay.py::relay_pending via
    `manage.py relay_outbox --model <app>.<Model> --exchange <module>.events`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=100)
    event_type = models.CharField(max_length=150)
    schema_version = models.PositiveIntegerField(default=1)
    payload = models.JSONField()
    correlation_id = models.UUIDField()
    causation_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=OutboxEventStatus.choices, default=OutboxEventStatus.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        # Matches the relay's own `WHERE status = 'pending' ORDER BY created_at` poll query
        # (ADR 0005) exactly, so every concrete subclass's table gets this index for free.
        indexes = [models.Index(fields=["status", "created_at"])]
