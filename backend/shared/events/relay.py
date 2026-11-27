"""Generic Transactional Outbox relay poller (ADR 0005) -- the `SELECT ... FOR UPDATE SKIP
LOCKED` poll loop every publishing module's concrete AbstractOutboxEvent subclass reuses
without a second design pass. Invoked via `manage.py relay_outbox`, wired by
shared/management/commands/relay_outbox.py (that file exists only because Django's
management-command discovery requires `<app>/management/commands/<name>.py`)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import pika
from django.db import transaction
from django.utils import timezone

from shared.events.outbox import AbstractOutboxEvent, OutboxEventStatus
from shared.events.publisher import ConfirmedPublisher

logger = logging.getLogger(__name__)

# ADR 0005's PII constraint: a log line may name event_id/event_type/correlation_id, never
# the full payload. `last_error` below only ever holds a pika/broker exception's own message,
# which cannot contain payload content.
_LAST_ERROR_MAX_LENGTH = 500


@dataclass
class RelayResult:
    published: int
    failed: int


def relay_pending(
    model: type[AbstractOutboxEvent],
    *,
    exchange: str,
    connection_parameters: pika.ConnectionParameters,
    limit: int = 100,
) -> RelayResult:
    """Publishes up to `limit` pending rows of `model` to `exchange`, using publisher
    confirms. If the broker is unreachable, every pending row picked up by this poll is left
    `pending` with `attempts`/`last_error` updated instead of being lost (ADR 0005)."""
    try:
        with ConfirmedPublisher(connection_parameters) as publisher:
            return _publish_pending(model, publisher=publisher, exchange=exchange, limit=limit)
    except pika.exceptions.AMQPConnectionError as exc:
        # pika's own AMQPConnectionError often carries an empty message (the real detail is
        # in __cause__/logs) -- build a message that is never blank, since this is what
        # `last_error` records below.
        message = (
            f"Could not connect to RabbitMQ at "
            f"{connection_parameters.host}:{connection_parameters.port}: {exc!r}"
        )
        logger.warning(message)
        return _mark_all_pending_failed(model, limit=limit, error=message)


def _publish_pending(
    model: type[AbstractOutboxEvent], *, publisher: ConfirmedPublisher, exchange: str, limit: int
) -> RelayResult:
    published = failed = 0
    publisher.declare_exchange(exchange=exchange)
    with transaction.atomic():
        rows = list(
            model.objects.select_for_update(skip_locked=True)
            .filter(status=OutboxEventStatus.PENDING)
            .order_by("created_at")[:limit]
        )
        for row in rows:
            routing_key = f"{row.event_type}.v{row.schema_version}"
            body = json.dumps(_envelope(row, producer=model._meta.app_label)).encode()
            try:
                publisher.publish(exchange=exchange, routing_key=routing_key, body=body)
            except pika.exceptions.UnroutableError as exc:
                row.attempts += 1
                row.last_error = str(exc)[:_LAST_ERROR_MAX_LENGTH]
                row.save(update_fields=["attempts", "last_error"])
                failed += 1
                continue
            row.status = OutboxEventStatus.PUBLISHED
            row.published_at = timezone.now()
            row.save(update_fields=["status", "published_at"])
            published += 1
    return RelayResult(published=published, failed=failed)


def _mark_all_pending_failed(
    model: type[AbstractOutboxEvent], *, limit: int, error: str
) -> RelayResult:
    message = error[:_LAST_ERROR_MAX_LENGTH]
    with transaction.atomic():
        rows = list(
            model.objects.select_for_update(skip_locked=True)
            .filter(status=OutboxEventStatus.PENDING)
            .order_by("created_at")[:limit]
        )
        for row in rows:
            row.attempts += 1
            row.last_error = message
            row.save(update_fields=["attempts", "last_error"])
    return RelayResult(published=0, failed=len(rows))


def _envelope(row: AbstractOutboxEvent, *, producer: str) -> dict:
    """ADR 0005's envelope shape. `aggregate_type`/`aggregate_id` are Outbox bookkeeping
    columns, not envelope fields -- a publishing module includes them in `payload` itself if
    a consumer needs them."""
    return {
        "event_id": str(row.id),
        "event_type": row.event_type,
        "schema_version": row.schema_version,
        "occurred_at": row.created_at.isoformat(),
        "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        "causation_id": str(row.causation_id) if row.causation_id else None,
        "producer": producer,
        "payload": row.payload,
    }
