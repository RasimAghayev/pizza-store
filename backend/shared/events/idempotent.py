from django.db import models


class AbstractProcessedEvent(models.Model):
    """Idempotent-consumer base table (ADR 0005) -- each consuming module subclasses this for
    its own concrete `processed_events` table. shared/events/consumer.py::IdempotentConsumer
    relies on the unique (event_id, consumer_name) pair so a redelivered event's business
    side effect is guaranteed to run at most once per consumer."""

    event_id = models.UUIDField()
    consumer_name = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        unique_together = [("event_id", "consumer_name")]
