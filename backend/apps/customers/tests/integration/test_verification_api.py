import json
from typing import cast

import pytest
from django.core.cache import cache

from apps.customers.tests.factories import CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

EMAIL_REQUEST_URL = "/api/v1/customers/verify/email/request/"
EMAIL_CONFIRM_URL = "/api/v1/customers/verify/email/confirm/"
PHONE_REQUEST_URL = "/api/v1/customers/verify/phone/request/"
PHONE_CONFIRM_URL = "/api/v1/customers/verify/phone/confirm/"


@pytest.fixture(autouse=True)
def _clear_cache():
    """OTP codes and throttle counters both live in the Redis-backed cache (settings.py
    CACHES), which persists across tests in the same run -- same rationale as
    apps/identity/tests/integration/test_auth.py's _clear_throttle_cache fixture."""
    cache.clear()
    yield
    cache.clear()


def _authenticated(client, *, phone: str | None = None):
    user = cast(User, UserFactory())
    customer = CustomerFactory(user_id=user.pk, phone=phone)
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return user, customer


def _post_json(client, url, payload=None):
    return client.post(url, data=json.dumps(payload or {}), content_type="application/json")


def _code_from(body: str) -> str:
    return body.split("Your verification code is ")[1].split(".")[0]


@pytest.mark.django_db
def test_anonymous_request_is_rejected(client):
    response = _post_json(client, EMAIL_REQUEST_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_email_verification_round_trip_succeeds(client, mailoutbox):
    _authenticated(client)

    request_response = _post_json(client, EMAIL_REQUEST_URL)
    assert request_response.status_code == 200

    code = _code_from(mailoutbox[-1].body)
    confirm_response = _post_json(client, EMAIL_CONFIRM_URL, {"code": code})

    assert confirm_response.status_code == 200
    assert confirm_response.json()["email_verified_at"] is not None


@pytest.mark.django_db
def test_email_verification_confirm_with_wrong_code_fails(client):
    _authenticated(client)
    _post_json(client, EMAIL_REQUEST_URL)

    response = _post_json(client, EMAIL_CONFIRM_URL, {"code": "000000"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_phone_verification_request_without_a_phone_on_file_fails(client):
    _authenticated(client, phone=None)

    response = _post_json(client, PHONE_REQUEST_URL)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_verifying_both_channels_upgrades_to_verified_customer(client, mailoutbox, caplog):
    _authenticated(client, phone="555-0100")

    _post_json(client, EMAIL_REQUEST_URL)
    email_confirm = _post_json(client, EMAIL_CONFIRM_URL, {"code": _code_from(mailoutbox[-1].body)})
    assert email_confirm.status_code == 200

    with caplog.at_level("INFO"):
        phone_request = _post_json(client, PHONE_REQUEST_URL)
    assert phone_request.status_code == 200
    sms_log = next(record.message for record in caplog.records if "SMS to" in record.message)

    phone_confirm = _post_json(client, PHONE_CONFIRM_URL, {"code": _code_from(sms_log)})

    assert phone_confirm.status_code == 200
    assert phone_confirm.json()["phone_verified_at"] is not None
