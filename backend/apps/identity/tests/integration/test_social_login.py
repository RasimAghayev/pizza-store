import json

import pytest
from allauth.socialaccount.models import SocialAccount
from django.core.cache import cache
from django.test import Client

from apps.customers.models.customer import Customer
from apps.customers.services.registration_service import RegistrationService
from apps.identity.domain.rbac import RoleCode
from apps.identity.models import RoleAssignment, User
from apps.identity.services.token_service import TokenService

SOCIAL_LOGIN_URL = "/api/v1/auth/social/{provider}/"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Throttle counters live in the Redis-backed cache (settings.py CACHES), which persists
    across tests in the same run -- same rationale as test_auth.py's own fixture."""
    cache.clear()
    yield
    cache.clear()


def _post(client, provider, payload, *, client_type="native"):
    return client.post(
        SOCIAL_LOGIN_URL.format(provider=provider),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE=client_type,
    )


def _patch_google(monkeypatch, *, sub, email, email_verified):
    """Mocks only allauth's call out to Google's own servers (the ID token's JWKS-backed
    signature/claims verification) -- everything downstream (sociallogin_from_response,
    complete_social_login, this project's own adapter) runs for real."""
    monkeypatch.setattr(
        "allauth.socialaccount.providers.google.views._verify_and_decode",
        lambda app, credential, verify_signature=True: {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "given_name": "Test",
            "family_name": "User",
        },
    )
    return {"id_token": "fake-google-id-token"}


def _patch_apple(monkeypatch, *, sub, email, email_verified):
    from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter

    monkeypatch.setattr(
        AppleOAuth2Adapter,
        "get_verified_identity_data",
        classmethod(
            lambda cls, provider, id_token: {
                "sub": sub,
                "email": email,
                "email_verified": email_verified,
            }
        ),
    )
    return {"id_token": "fake-apple-id-token"}


def _patch_facebook(monkeypatch, *, sub, email, email_verified):
    """FacebookProvider.extract_email_addresses always reports verified=False (allauth's own
    implementation -- Graph API's `verified` field does not prove email ownership), so
    `email_verified` has no effect here; kept for a uniform fixture signature across
    providers. The fake replacement still calls the real sociallogin_from_response so that
    logic stays exercised, same as the other two providers -- only the Graph API round-trips
    (debug_token, /me) are skipped."""
    del email_verified

    def _fake_verify_token(request, provider, access_token, auth_type="", auth_nonce=""):
        return provider.sociallogin_from_response(
            request, {"id": sub, "email": email, "name": "Test User"}
        )

    monkeypatch.setattr(
        "allauth.socialaccount.providers.facebook.flows.verify_token", _fake_verify_token
    )
    return {"access_token": "fake-facebook-access-token"}


_PATCHERS = {"google": _patch_google, "apple": _patch_apple, "facebook": _patch_facebook}


@pytest.mark.django_db
@pytest.mark.parametrize("provider", ["google", "apple", "facebook"])
def test_new_social_login_creates_user_customer_role_and_real_tokens(client, monkeypatch, provider):
    email = f"{provider}-new-user@example.com"
    payload = _PATCHERS[provider](
        monkeypatch, sub=f"{provider}-uid-1", email=email, email_verified=True
    )

    response = _post(client, provider, payload)

    assert response.status_code == 200
    body = response.json()
    claims = TokenService().verify_access_token(body["access_token"])

    user = User.objects.get(email=email)
    assert str(user.pk) == claims["sub"]
    assert Customer.objects.filter(user_id=user.pk).exists()
    assert RoleAssignment.objects.filter(user=user, role_code=RoleCode.CUSTOMER).exists()
    assert SocialAccount.objects.filter(
        user=user, provider=provider, uid=f"{provider}-uid-1"
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("provider", ["google", "apple", "facebook"])
def test_second_social_login_with_the_same_identity_reuses_the_existing_user(
    client, monkeypatch, provider
):
    email = f"{provider}-returning-user@example.com"
    payload = _PATCHERS[provider](
        monkeypatch, sub=f"{provider}-uid-2", email=email, email_verified=True
    )

    first_response = _post(client, provider, payload)
    assert first_response.status_code == 200
    user_id = User.objects.get(email=email).pk

    second_response = _post(client, provider, payload)

    assert second_response.status_code == 200
    assert User.objects.filter(email=email).count() == 1
    assert Customer.objects.filter(user_id=user_id).count() == 1
    assert User.objects.get(email=email).pk == user_id


@pytest.mark.django_db
def test_social_login_with_a_verified_email_colliding_with_an_existing_unlinked_account_is_rejected(
    client, monkeypatch
):
    existing_customer = RegistrationService().register(
        email="collision@example.com", password="correct-horse-battery-staple"
    )
    payload = _patch_google(
        monkeypatch,
        sub="google-uid-collide",
        email="collision@example.com",
        email_verified=True,
    )

    response = _post(client, "google", payload)

    assert response.status_code == 400
    assert "account_exists_unlinked" in response.json()["error"]["details"]
    assert not SocialAccount.objects.filter(user_id=existing_customer.user_id).exists()
    assert User.objects.filter(email="collision@example.com").count() == 1
    assert Customer.objects.filter(user_id=existing_customer.user_id).count() == 1


@pytest.mark.django_db
def test_facebook_login_with_a_colliding_email_never_merges_into_the_existing_account(
    client, monkeypatch
):
    """Facebook never reports a verified email (see _patch_facebook's own docstring), so
    PizzaStoreSocialAccountAdapter.pre_social_login's verified-only match never fires here;
    allauth's own signup flow then refuses auto-signup for an already-taken email
    (assess_unique_email) and never creates a user. This only pins down that the collision
    still fails closed -- no account is silently merged into, no new User row is created --
    not that it produces the account_exists_unlinked message, which deliberately requires a
    verified email (see test above) so this always-unverified path can't be used as an
    email-existence oracle."""
    existing_customer = RegistrationService().register(
        email="fb-collision@example.com", password="correct-horse-battery-staple"
    )
    payload = _patch_facebook(
        monkeypatch,
        sub="facebook-uid-collide",
        email="fb-collision@example.com",
        email_verified=True,
    )

    response = _post(client, "facebook", payload)

    assert response.status_code != 200
    assert not SocialAccount.objects.filter(user_id=existing_customer.user_id).exists()
    assert User.objects.filter(email="fb-collision@example.com").count() == 1


@pytest.mark.django_db
def test_social_login_never_sets_an_allauth_session_cookie(client, monkeypatch):
    payload = _patch_google(
        monkeypatch, sub="google-uid-3", email="cookie-check@example.com", email_verified=True
    )

    response = _post(client, "google", payload)

    assert response.status_code == 200
    assert "sessionid" not in response.cookies


@pytest.mark.django_db
def test_unknown_provider_returns_404(client):
    response = _post(client, "not-a-real-provider", {"id_token": "whatever"})

    assert response.status_code == 404


@pytest.mark.django_db
def test_browser_client_uses_cookies(monkeypatch):
    """Uses a CSRF-enforcing Client explicitly, same rationale as test_auth.py's own browser
    test: pytest-django's `client` fixture disables CSRF enforcement by default."""
    client = Client(enforce_csrf_checks=True)
    payload = _patch_google(
        monkeypatch, sub="google-uid-4", email="browser-check@example.com", email_verified=True
    )

    response = client.post(
        SOCIAL_LOGIN_URL.format(provider="google"),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="browser",
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Login successful."}
    access_cookie = response.cookies["access_token"]
    refresh_cookie = response.cookies["refresh_token"]
    assert access_cookie["httponly"]
    assert access_cookie["samesite"] == "Strict"
    assert refresh_cookie["path"] == "/api/v1/auth"
