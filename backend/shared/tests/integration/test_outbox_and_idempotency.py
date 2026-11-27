"""Integration test for shared/events/{outbox.py,idempotent.py,publisher.py,relay.py,
consumer.py} (Issue #130) -- runs against the real Compose `rabbitmq` + `postgres` services,
per ADR 0005. Declares and tears down its own test-only exchange/queues; never touches the
real 8-exchange topology or docs/messaging/event-catalog.md."""

import json
import uuid

import pika
import pytest
from django.core.management import call_command

from health.models import HealthOutboxEvent, HealthProcessedEvent
from shared.events.consumer import IdempotentConsumer
from shared.events.outbox import OutboxEventStatus
from shared.events.publisher import connection_parameters

_EXCHANGE = "test.outbox-idempotency.exchange"
_ROUTING_KEY = "test.outbox_idempotency_fixture.v1"


@pytest.fixture
def rabbitmq_channel():
    connection = pika.BlockingConnection(connection_parameters())
    channel = connection.channel()
    channel.exchange_declare(exchange=_EXCHANGE, exchange_type="topic", durable=True)
    yield channel
    channel.exchange_delete(exchange=_EXCHANGE)
    connection.close()


class _CountingConsumer(IdempotentConsumer):
    queue = "test.idempotent-consumer.q"
    exchange = _EXCHANGE
    routing_key = _ROUTING_KEY
    consumer_name = "test-counting-consumer"
    processed_event_model = HealthProcessedEvent

    def __init__(self):
        self.handled_count = 0

    def handle(self, envelope):
        self.handled_count += 1


@pytest.mark.django_db(transaction=True)
def test_outbox_row_stays_pending_when_broker_unreachable_then_publishes_once_reachable(
    rabbitmq_channel,
):
    queue = "test.outbox-relay.q"
    rabbitmq_channel.queue_declare(queue=queue, durable=True)
    rabbitmq_channel.queue_bind(queue=queue, exchange=_EXCHANGE, routing_key=_ROUTING_KEY)

    row = HealthOutboxEvent.objects.create(
        aggregate_type="health_ping",
        aggregate_id=str(uuid.uuid4()),
        event_type="test.outbox_idempotency_fixture",
        schema_version=1,
        payload={"note": "outbox relay test"},
        correlation_id=uuid.uuid4(),
    )

    # Deliberately wrong port -- nothing listens here -- per Issue #130's Test A.
    call_command(
        "relay_outbox",
        model="health.HealthOutboxEvent",
        exchange=_EXCHANGE,
        host="127.0.0.1",
        port=59999,
    )

    row.refresh_from_db()
    assert row.status == OutboxEventStatus.PENDING
    assert row.attempts == 1
    assert row.last_error

    call_command("relay_outbox", model="health.HealthOutboxEvent", exchange=_EXCHANGE)

    row.refresh_from_db()
    assert row.status == OutboxEventStatus.PUBLISHED
    assert row.published_at is not None

    rabbitmq_channel.queue_delete(queue=queue)


@pytest.mark.django_db(transaction=True)
def test_idempotent_consumer_processes_a_duplicate_delivery_exactly_once(rabbitmq_channel):
    consumer = _CountingConsumer()
    consumer.declare_topology(rabbitmq_channel)

    event_id = str(uuid.uuid4())
    body = json.dumps(
        {
            "event_id": event_id,
            "event_type": "test.outbox_idempotency_fixture",
            "schema_version": 1,
            "payload": {},
        }
    ).encode()

    rabbitmq_channel.basic_publish(exchange=_EXCHANGE, routing_key=_ROUTING_KEY, body=body)
    rabbitmq_channel.basic_publish(exchange=_EXCHANGE, routing_key=_ROUTING_KEY, body=body)

    for _ in range(2):
        method, properties, delivered_body = rabbitmq_channel.basic_get(
            queue=consumer.queue, auto_ack=False
        )
        assert method is not None, "expected a queued delivery"
        consumer._on_message(rabbitmq_channel, method, properties, delivered_body)

    assert consumer.handled_count == 1
    assert (
        HealthProcessedEvent.objects.filter(
            event_id=event_id, consumer_name=consumer.consumer_name
        ).count()
        == 1
    )

    rabbitmq_channel.queue_delete(queue=consumer.queue)
    rabbitmq_channel.queue_delete(queue=f"{consumer.queue}.retry")
    rabbitmq_channel.queue_delete(queue=f"{consumer.queue}.dlq")
