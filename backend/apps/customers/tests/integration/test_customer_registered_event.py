"""Proves CustomerRegistered goes out through the real Outbox relay to a real RabbitMQ
queue bound to the real `customers.events` exchange / `customer.registered.v1` routing key
(Issue #176) -- mirrors shared/tests/integration/test_outbox_and_idempotency.py's proof
pattern (Issue #130), but against the actual catalog topology rather than a throwaway test
exchange, since this Task is "the first real module to publish" it
(docs/messaging/event-catalog.md)."""

import json

import pika
import pytest
from django.core.management import call_command
from faker import Faker

from apps.customers.events.customer_registered import EXCHANGE
from apps.customers.models.customer_outbox_event import CustomerOutboxEvent
from apps.customers.services.registration_service import RegistrationService
from shared.events.outbox import OutboxEventStatus
from shared.events.publisher import connection_parameters

fake = Faker()

_ROUTING_KEY = "customer.registered.v1"
_QUEUE = "test.customer-registered-proof.q"


@pytest.fixture
def rabbitmq_channel():
    connection = pika.BlockingConnection(connection_parameters())
    channel = connection.channel()
    channel.queue_declare(queue=_QUEUE, durable=True)
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_bind(queue=_QUEUE, exchange=EXCHANGE, routing_key=_ROUTING_KEY)
    yield channel
    channel.queue_delete(queue=_QUEUE)
    connection.close()


@pytest.mark.django_db(transaction=True)
def test_relay_delivers_customer_registered_to_a_real_queue(rabbitmq_channel):
    email = fake.email()
    RegistrationService().register(email=email, password=fake.password())
    event = CustomerOutboxEvent.objects.get()

    call_command("relay_outbox", model="customers.CustomerOutboxEvent", exchange=EXCHANGE)

    event.refresh_from_db()
    assert event.status == OutboxEventStatus.PUBLISHED

    method, _properties, body = rabbitmq_channel.basic_get(queue=_QUEUE, auto_ack=True)
    assert method is not None, "expected a queued delivery"
    envelope = json.loads(body)
    assert envelope["event_type"] == "customer.registered"
    assert envelope["schema_version"] == 1
    assert envelope["producer"] == "customers"
    assert envelope["payload"]["email"] == email.strip().lower()
