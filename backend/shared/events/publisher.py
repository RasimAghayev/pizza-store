"""Low-level publisher-confirmed RabbitMQ wrapper (ADR 0005). Knows nothing about Outbox
rows -- shared/events/relay.py::relay_pending is the caller that decides how to record
success/failure against a concrete AbstractOutboxEvent subclass."""

from __future__ import annotations

from types import TracebackType

import pika
from django.conf import settings
from pika.adapters.blocking_connection import BlockingChannel


def connection_parameters(
    *, host: str | None = None, port: int | None = None
) -> pika.ConnectionParameters:
    """Builds connection parameters from settings.RABBITMQ_* (ADR 0006 secret handling) by
    default; `host`/`port` overrides exist only so a test can point the relay at an
    unreachable broker without touching real configuration."""
    return pika.ConnectionParameters(
        host=host if host is not None else settings.RABBITMQ_HOST,
        port=port if port is not None else settings.RABBITMQ_PORT,
        credentials=pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD),
        connection_attempts=1,
        socket_timeout=5,
    )


class ConfirmedPublisher:
    """Context manager around one pika.BlockingConnection/channel pair with publisher
    confirms enabled (ADR 0005's "publishers use publisher confirms" requirement).

    Raises `pika.exceptions.AMQPConnectionError` on `__enter__` if the broker is unreachable;
    `publish()` raises `pika.exceptions.UnroutableError` if that specific message is
    nacked/unroutable. Neither exception is caught here -- the caller (relay.py) decides how
    to record the failure against an Outbox row."""

    def __init__(self, parameters: pika.ConnectionParameters) -> None:
        self._parameters = parameters
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def __enter__(self) -> ConfirmedPublisher:
        self._connection = pika.BlockingConnection(self._parameters)
        self._channel = self._connection.channel()
        self._channel.confirm_delivery()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            self._connection.close()

    def publish(self, *, exchange: str, routing_key: str, body: bytes) -> None:
        if self._channel is None:
            raise RuntimeError("publish() called outside the `with` block")
        self._channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            mandatory=True,
        )
