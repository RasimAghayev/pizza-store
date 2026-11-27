import pytest
from faker import Faker

from apps.identity.repositories.user_repository import UserRepository

fake = Faker()


@pytest.mark.django_db
def test_create_persists_a_user_with_a_hashed_password():
    repository = UserRepository()
    password = fake.password()

    user = repository.create(email="new.user@example.com", password=password)

    assert user.pk is not None
    assert user.password != password
    assert user.check_password(password)


@pytest.mark.django_db
def test_get_by_email_is_case_insensitive():
    repository = UserRepository()
    created = repository.create(email="Case.Insensitive@Example.com", password=fake.password())

    found = repository.get_by_email("case.insensitive@example.com")

    assert found is not None
    assert found.email == created.email


@pytest.mark.django_db
def test_get_by_email_returns_none_when_not_found():
    repository = UserRepository()

    assert repository.get_by_email("nobody@example.com") is None
