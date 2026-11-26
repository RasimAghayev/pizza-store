import pytest

from apps.identity.repositories.user_repository import UserRepository


@pytest.mark.django_db
def test_create_persists_a_user_with_a_hashed_password():
    repository = UserRepository()

    user = repository.create(email="new.user@example.com", password="Str0ngP@ssw0rd!")

    assert user.pk is not None
    assert user.password != "Str0ngP@ssw0rd!"
    assert user.check_password("Str0ngP@ssw0rd!")


@pytest.mark.django_db
def test_get_by_email_is_case_insensitive():
    repository = UserRepository()
    created = repository.create(email="Case.Insensitive@Example.com", password="Str0ngP@ssw0rd!")

    found = repository.get_by_email("case.insensitive@example.com")

    assert found is not None
    assert found.email == created.email


@pytest.mark.django_db
def test_get_by_email_returns_none_when_not_found():
    repository = UserRepository()

    assert repository.get_by_email("nobody@example.com") is None
