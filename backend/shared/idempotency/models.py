from django.db import models


class IdempotencyKey(models.Model):
    """Guards a client-retried, side-effecting HTTP request (e.g. order checkout, payment
    capture -- Issues #197/#198) against duplicate execution. Distinct from
    `shared.events.idempotent.AbstractProcessedEvent`: that table de-duplicates a RabbitMQ
    message *delivery* on the consumer side (ADR 0005); this table has no broker involvement
    at all -- it guards a client's own repeated HTTP request, identified by the
    `Idempotency-Key` header it sends. Written and read only through
    `shared.idempotency.service.IdempotencyService`; see `shared.idempotency.drf` for the DRF
    entry point views use.
    """

    key = models.CharField(max_length=255)
    scope = models.CharField(max_length=100)
    user_id = models.PositiveBigIntegerField()
    request_fingerprint = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["key", "scope"], name="unique_idempotency_key_scope")
        ]

    def __str__(self) -> str:
        return f"IdempotencyKey(key={self.key!r}, scope={self.scope!r})"
