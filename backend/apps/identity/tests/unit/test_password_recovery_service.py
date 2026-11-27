import hashlib

import pytest
from django.core.cache import cache

from apps.identity.services.password_recovery_service import (
    InvalidResetTokenError,
    PasswordRecoveryService,
)
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

PASSWORD = "correct-horse-battery-staple"
NEW_PASSWORD = "a-different-battery-staple"
FIXED_TOKEN = "deterministic-test-token"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _fixed_reset_token(monkeypatch):
    """Pins secrets.token_urlsafe's output so tests can assert against a known token value
    instead of parsing the console-email body (an implementation detail of the logged
    notification, not of the service's own contract)."""
    monkeypatch.setattr(
        "apps.identity.services.password_recovery_service._generate_raw_token",
        lambda: FIXED_TOKEN,
    )


@pytest.fixture(autouse=True)
def _stub_email(monkeypatch):
    monkeypatch.setattr(
        "apps.identity.services.password_recovery_service.send_console_email", lambda **_: None
    )


@pytest.mark.django_db
def test_request_reset_for_a_known_email_stores_the_hashed_token():
    user = UserFactory(password=PASSWORD)

    PasswordRecoveryService().request_reset(user.email)

    key = f"pwreset:{hashlib.sha256(FIXED_TOKEN.encode()).hexdigest()}"
    assert cache.get(key) == user.pk


@pytest.mark.django_db
def test_request_reset_for_an_unknown_email_is_a_silent_no_op():
    PasswordRecoveryService().request_reset("nobody@example.com")

    key = f"pwreset:{hashlib.sha256(FIXED_TOKEN.encode()).hexdigest()}"
    assert cache.get(key) is None


@pytest.mark.django_db
def test_confirm_reset_with_the_right_token_sets_the_new_password():
    user = UserFactory(password=PASSWORD)
    PasswordRecoveryService().request_reset(user.email)

    PasswordRecoveryService().confirm_reset(token=FIXED_TOKEN, new_password=NEW_PASSWORD)

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_confirm_reset_is_single_use():
    user = UserFactory(password=PASSWORD)
    PasswordRecoveryService().request_reset(user.email)
    PasswordRecoveryService().confirm_reset(token=FIXED_TOKEN, new_password=NEW_PASSWORD)

    with pytest.raises(InvalidResetTokenError):
        PasswordRecoveryService().confirm_reset(
            token=FIXED_TOKEN, new_password="yet-another-password"
        )


@pytest.mark.django_db
def test_confirm_reset_with_an_unknown_token_raises():
    with pytest.raises(InvalidResetTokenError):
        PasswordRecoveryService().confirm_reset(token="not-a-real-token", new_password=NEW_PASSWORD)


@pytest.mark.django_db
def test_confirm_reset_revokes_every_existing_refresh_token_family():
    user = UserFactory(password=PASSWORD)
    token_service = TokenService()
    _, record_a = token_service.issue_refresh_token(user)
    _, record_b = token_service.issue_refresh_token(user)
    PasswordRecoveryService().request_reset(user.email)

    PasswordRecoveryService().confirm_reset(token=FIXED_TOKEN, new_password=NEW_PASSWORD)

    record_a.refresh_from_db()
    record_b.refresh_from_db()
    assert record_a.revoked_at is not None
    assert record_b.revoked_at is not None
