import json

import pytest
from django.core.cache import cache

from apps.identity.tests.factories import UserFactory

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
RESET_REQUEST_URL = "/api/v1/auth/password-reset/request/"
RESET_CONFIRM_URL = "/api/v1/auth/password-reset/confirm/"

PASSWORD = "correct-horse-battery-staple"
NEW_PASSWORD = "a-different-battery-staple"


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _post(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="native",
    )


def _code_from(body: str) -> str:
    return body.split("Use this token to reset your password: ")[1].split(".")[0]


@pytest.mark.django_db
def test_request_reset_always_returns_the_same_generic_response(client, mailoutbox):
    user = UserFactory(password=PASSWORD)

    known_response = client.post(
        RESET_REQUEST_URL, data=json.dumps({"email": user.email}), content_type="application/json"
    )
    unknown_response = client.post(
        RESET_REQUEST_URL,
        data=json.dumps({"email": "nobody@example.com"}),
        content_type="application/json",
    )

    assert known_response.status_code == 200
    assert unknown_response.status_code == 200
    assert known_response.json() == unknown_response.json()
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_reset_round_trip_sets_the_new_password_and_revokes_existing_sessions(client, mailoutbox):
    user = UserFactory(password=PASSWORD)
    login_body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    old_refresh_token = login_body["refresh_token"]

    client.post(
        RESET_REQUEST_URL, data=json.dumps({"email": user.email}), content_type="application/json"
    )
    token = _code_from(mailoutbox[-1].body)

    confirm_response = client.post(
        RESET_CONFIRM_URL,
        data=json.dumps({"token": token, "new_password": NEW_PASSWORD}),
        content_type="application/json",
    )
    assert confirm_response.status_code == 200

    old_login = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD})
    assert old_login.status_code == 401

    new_login = _post(client, LOGIN_URL, {"email": user.email, "password": NEW_PASSWORD})
    assert new_login.status_code == 200

    # Reuse Issue #129's stolen-token test pattern: every pre-reset refresh token must now
    # be rejected, proving the whole family was revoked, not just the one presented at login.
    blocked_refresh = _post(client, REFRESH_URL, {"refresh_token": old_refresh_token})
    assert blocked_refresh.status_code == 401


@pytest.mark.django_db
def test_confirm_with_an_unknown_token_fails(client):
    response = client.post(
        RESET_CONFIRM_URL,
        data=json.dumps({"token": "not-a-real-token", "new_password": NEW_PASSWORD}),
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_confirm_is_single_use(client, mailoutbox):
    user = UserFactory(password=PASSWORD)
    client.post(
        RESET_REQUEST_URL, data=json.dumps({"email": user.email}), content_type="application/json"
    )
    token = _code_from(mailoutbox[-1].body)
    client.post(
        RESET_CONFIRM_URL,
        data=json.dumps({"token": token, "new_password": NEW_PASSWORD}),
        content_type="application/json",
    )

    second_attempt = client.post(
        RESET_CONFIRM_URL,
        data=json.dumps({"token": token, "new_password": "yet-another-password"}),
        content_type="application/json",
    )

    assert second_attempt.status_code == 401
