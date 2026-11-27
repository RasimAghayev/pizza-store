import pytest

from apps.identity.services.authentication_service import AuthenticationService
from apps.identity.tests.factories import UserFactory


@pytest.mark.django_db
def test_verify_credentials_succeeds_with_correct_password():
    user = UserFactory(password="correct-password")

    result = AuthenticationService().verify_credentials(user.email, "correct-password")

    assert result == user


@pytest.mark.django_db
def test_verify_credentials_fails_with_wrong_password():
    user = UserFactory(password="correct-password")

    result = AuthenticationService().verify_credentials(user.email, "wrong-password")

    assert result is None


@pytest.mark.django_db
def test_verify_credentials_fails_for_unknown_email():
    result = AuthenticationService().verify_credentials("nobody@example.com", "irrelevant")

    assert result is None
