from django.db import models

from shared.events.idempotent import AbstractProcessedEvent
from shared.events.outbox import AbstractOutboxEvent


class HealthPing(models.Model):
    """Exists purely to give Task #108/#110 a real migration to exercise end-to-end."""

    note = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class HealthOutboxEvent(AbstractOutboxEvent):
    """Throwaway concrete Outbox subclass (Issue #130) -- gives
    shared/tests/integration/test_outbox_and_idempotency.py a real migrated table to exercise
    shared/events/relay.py against, reusing this app's existing migration history rather than
    standing up a second test-only Django app. Not a real business event source."""


class HealthProcessedEvent(AbstractProcessedEvent):
    """Throwaway concrete ProcessedEvent subclass (Issue #130) -- same rationale as
    HealthOutboxEvent above, for the idempotent-consumer test."""
