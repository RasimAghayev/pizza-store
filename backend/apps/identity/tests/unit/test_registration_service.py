import pytest
from faker import Faker

from apps.identity.services.registration_service import (
    EmailAlreadyRegisteredError,
    RegistrationService,
)

fake = Faker()


@pytest.mark.django_db
def test_register_creates_a_user_with_a_hashed_password():
    email = fake.email()
    password = fake.password()

    user = RegistrationService().register(email=email, password=password)

    assert user.pk is not None
    assert user.email == email.strip().lower()
    assert user.check_password(password)


@pytest.mark.django_db
def test_register_rejects_a_duplicate_email():
    email = fake.email()
    RegistrationService().register(email=email, password=fake.password())

    with pytest.raises(EmailAlreadyRegisteredError):
        RegistrationService().register(email=email, password=fake.password())
