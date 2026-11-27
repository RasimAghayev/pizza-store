import pytest
from faker import Faker

from apps.customers.models.customer import Customer
from apps.customers.models.customer_outbox_event import CustomerOutboxEvent
from apps.customers.services.registration_service import (
    EmailAlreadyRegisteredError,
    RegistrationService,
)
from apps.identity.domain.rbac import RoleCode
from apps.identity.models import RoleAssignment, User
from shared.events.outbox import OutboxEventStatus

fake = Faker()


@pytest.mark.django_db
def test_register_creates_a_user_a_customer_a_role_assignment_and_a_pending_event():
    email = fake.email()
    password = fake.password()

    customer = RegistrationService().register(email=email, password=password)

    assert isinstance(customer, Customer)
    user = User.objects.get(pk=customer.user_id)
    assert user.email == email.strip().lower()
    assert user.check_password(password)

    assert RoleAssignment.objects.filter(user=user, role_code=RoleCode.CUSTOMER).count() == 1

    event = CustomerOutboxEvent.objects.get()
    assert event.status == OutboxEventStatus.PENDING
    assert event.event_type == "customer.registered"
    assert event.schema_version == 1
    assert event.aggregate_type == "customer"
    assert event.aggregate_id == str(customer.user_id)
    assert event.payload["user_id"] == customer.user_id
    assert event.payload["email"] == user.email
    assert event.payload["registered_at"]


@pytest.mark.django_db
def test_register_rejects_a_duplicate_email_and_creates_no_rows():
    email = fake.email()
    RegistrationService().register(email=email, password=fake.password())

    with pytest.raises(EmailAlreadyRegisteredError):
        RegistrationService().register(email=email, password=fake.password())

    assert User.objects.filter(email=email.strip().lower()).count() == 1
    assert Customer.objects.count() == 1
    assert CustomerOutboxEvent.objects.count() == 1
