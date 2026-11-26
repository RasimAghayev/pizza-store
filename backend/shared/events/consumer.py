"""Idempotent-consumer base class and retry/DLQ topology (ADR 0005). Each consuming module
subclasses `IdempotentConsumer`, binding it to its own `shared/events/idempotent.py
::AbstractProcessedEvent` subclass -- that table's unique (event_id, consumer_name)
constraint is what guarantees a redelivered event's `handle()` runs at most once."""

from __future__ import annotations

import json
import logging
from typing import Any

import pika
from django.db import models, transaction

logger = logging.getLogger(__name__)

# ADR 0005's backoff schedule: 3 retry attempts at 30s, 2m, then 10m; the 4th failure is
# routed to the DLQ instead of back into the retry queue.
RETRY_BACKOFF_MS: tuple[int, ...] = (30_000, 120_000, 600_000)

_RETRY_COUNT_HEADER = "x-retry-count"


def next_retry_delay_ms(retry_count: int) -> int | None:
    """Returns the backoff delay (ms) for this failure, or None once ADR 0005's 3-attempt
    schedule is exhausted and the message belongs in the DLQ instead."""
    if retry_count < len(RETRY_BACKOFF_MS):
        return RETRY_BACKOFF_MS[retry_count]
    return None


def declare_topology(channel: Any, *, queue: str, exchange: str, routing_key: str) -> None:
    """Declares `<queue>` bound to `exchange`/`routing_key`, its retry queue `<queue>.retry`
    (dead-lettering back at that same exchange/routing key once a republished message's own
    per-message TTL expires -- the queue carries no queue-level `x-message-ttl` itself since
    each ADR 0005 backoff step needs a different delay), and its parking-lot `<queue>.dlq`.
    Idempotent: safe to call on every consumer startup."""
    channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
    channel.queue_declare(queue=queue, durable=True)
    channel.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)
    channel.queue_declare(
        queue=f"{queue}.retry",
        durable=True,
        arguments={
            "x-dead-letter-exchange": exchange,
            "x-dead-letter-routing-key": routing_key,
        },
    )
    channel.queue_declare(queue=f"{queue}.dlq", durable=True)


class IdempotentConsumer:
    """calls `processed_event_model` (an AbstractProcessedEvent subclass) -- see
    shared/events/idempotent.py. Subclasses set the four class attributes below and
    implement `handle()` with their business side effect."""

    queue: str
    exchange: str
    routing_key: str
    consumer_name: str
    processed_event_model: type[models.Model]
    prefetch_count: int = 10

    def handle(self, envelope: dict) -> None:
        raise NotImplementedError

    def declare_topology(self, channel: Any) -> None:
        declare_topology(
            channel, queue=self.queue, exchange=self.exchange, routing_key=self.routing_key
        )

    def consume(self, channel: Any) -> None:
        self.declare_topology(channel)
        channel.basic_qos(prefetch_count=self.prefetch_count)
        channel.basic_consume(
            queue=self.queue, on_message_callback=self._on_message, auto_ack=False
        )

    def _on_message(self, channel: Any, method: Any, properties: Any, body: bytes) -> None:
        envelope = json.loads(body)
        retry_count = (properties.headers or {}).get(_RETRY_COUNT_HEADER, 0)
        try:
            self._process_once(envelope)
        except Exception as exc:  # noqa: BLE001 -- any handler failure routes to retry/DLQ,
            # it must never crash the consumer loop itself (ADR 0005's DLQ requirement).
            logger.warning(
                "Event %s failed in consumer %s: %s",
                envelope.get("event_id"),
                self.consumer_name,
                exc,
            )
            self._retry_or_dlq(channel, body=body, retry_count=retry_count)
        channel.basic_ack(delivery_tag=method.delivery_tag)

    def _process_once(self, envelope: dict) -> None:
        with transaction.atomic():
            # Idiomatic-Django equivalent of ADR 0005's literal "INSERT ... ON CONFLICT
            # (event_id, consumer_name) DO NOTHING": get_or_create's own
            # IntegrityError-and-retry implementation already gives the same at-most-once
            # guarantee without hand-written raw SQL.
            _, created = self.processed_event_model.objects.get_or_create(
                event_id=envelope["event_id"], consumer_name=self.consumer_name
            )
            if created:
                self.handle(envelope)

    def _retry_or_dlq(self, channel: Any, *, body: bytes, retry_count: int) -> None:
        delay_ms = next_retry_delay_ms(retry_count)
        if delay_ms is None:
            channel.basic_publish(exchange="", routing_key=f"{self.queue}.dlq", body=body)
            return
        channel.basic_publish(
            exchange="",
            routing_key=f"{self.queue}.retry",
            body=body,
            properties=pika.BasicProperties(
                expiration=str(delay_ms), headers={_RETRY_COUNT_HEADER: retry_count + 1}
            ),
        )
