import hashlib
import json

import pytest
from django.core.cache import cache
from django.test import Client

from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"

PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttle counters live in the Redis-backed cache (settings.py CACHES), which persists
    across tests in the same run -- without this, an earlier test's login attempts would
    count against a later test's rate-limit assertions."""
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


@pytest.mark.django_db
def test_login_issues_a_verifiable_access_token_and_persists_a_hashed_refresh_token(client):
    user = UserFactory(password=PASSWORD)

    response = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()

    claims = TokenService().verify_access_token(body["access_token"])
    assert claims["sub"] == str(user.pk)

    record = user.refresh_tokens.get()
    assert record.token_hash == hashlib.sha256(body["refresh_token"].encode()).hexdigest()
    assert record.revoked_at is None


@pytest.mark.django_db
def test_refresh_rotates_the_refresh_token_and_rejects_the_old_one(client):
    user = UserFactory(password=PASSWORD)
    login_body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    old_refresh_token = login_body["refresh_token"]

    refresh_response = _post(client, REFRESH_URL, {"refresh_token": old_refresh_token})
    assert refresh_response.status_code == 200
    new_refresh_token = refresh_response.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token

    reuse_response = _post(client, REFRESH_URL, {"refresh_token": old_refresh_token})
    assert reuse_response.status_code == 401


@pytest.mark.django_db
def test_reusing_a_rotated_refresh_token_revokes_the_whole_family(client):
    user = UserFactory(password=PASSWORD)
    login_body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    original_refresh_token = login_body["refresh_token"]

    rotated_body = _post(client, REFRESH_URL, {"refresh_token": original_refresh_token}).json()
    legitimate_next_token = rotated_body["refresh_token"]

    stolen_response = _post(client, REFRESH_URL, {"refresh_token": original_refresh_token})
    assert stolen_response.status_code == 401

    blocked_response = _post(client, REFRESH_URL, {"refresh_token": legitimate_next_token})
    assert blocked_response.status_code == 401


@pytest.mark.django_db
def test_browser_client_uses_cookies_and_refresh_enforces_csrf():
    """Uses a CSRF-enforcing Client explicitly -- pytest-django's `client` fixture sets
    Django's `_dont_enforce_csrf_checks` by default (documented test-client convenience),
    which would make shared/api/csrf.py::enforce_csrf's rejection path untestable here."""
    client = Client(enforce_csrf_checks=True)
    user = UserFactory(password=PASSWORD)

    login_response = client.post(
        LOGIN_URL,
        data=json.dumps({"email": user.email, "password": PASSWORD}),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="browser",
    )
    assert login_response.status_code == 200
    assert login_response.json() == {"message": "Login successful."}

    access_cookie = login_response.cookies["access_token"]
    refresh_cookie = login_response.cookies["refresh_token"]
    assert access_cookie["httponly"]
    assert access_cookie["samesite"] == "Strict"
    assert refresh_cookie["path"] == "/api/v1/auth"
    csrf_token = login_response.cookies["csrftoken"].value

    refresh_without_csrf = client.post(
        REFRESH_URL,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="browser",
    )
    assert refresh_without_csrf.status_code == 403

    refresh_with_csrf = client.post(
        REFRESH_URL,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="browser",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert refresh_with_csrf.status_code == 200

    logout_response = client.post(
        LOGOUT_URL,
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="browser",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert logout_response.status_code == 200

    # A real browser only attaches a Path-scoped cookie to requests whose path matches
    # that scope (RFC 6265) -- django.test.Client ignores Path entirely and would send
    # refresh_token regardless, so this assertion is the only thing in this test that
    # would have caught the refresh cookie's Path excluding LOGOUT_URL (a real bug found
    # via a real-browser Playwright run, not this suite -- see Issue #154).
    assert LOGOUT_URL.startswith(refresh_cookie["path"])
    assert REFRESH_URL.startswith(refresh_cookie["path"])


@pytest.mark.django_db
def test_login_is_rate_limited_per_account(client):
    user = UserFactory(password=PASSWORD)

    for _ in range(5):
        response = _post(client, LOGIN_URL, {"email": user.email, "password": "wrong-password"})
        assert response.status_code == 401

    throttled_response = _post(
        client, LOGIN_URL, {"email": user.email, "password": "wrong-password"}
    )
    assert throttled_response.status_code == 429
