from apps.customers.models.customer import Customer
from apps.customers.models.customer_outbox_event import CustomerOutboxEvent

__all__ = ["Customer", "CustomerOutboxEvent"]
