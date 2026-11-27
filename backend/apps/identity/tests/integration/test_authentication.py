import pytest
from django.test import RequestFactory
from rest_framework import exceptions
from rest_framework.request import Request

from apps.identity.api.authentication import JWTCookieOrHeaderAuthentication
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory


def _wrap(django_request):
    return Request(django_request)


def test_authenticate_returns_none_when_no_token_present():
    request = _wrap(RequestFactory().get("/"))

    assert JWTCookieOrHeaderAuthentication().authenticate(request) is None


@pytest.mark.django_db
def test_authenticate_resolves_user_from_bearer_header():
    user = UserFactory()
    token = TokenService().issue_access_token(user)
    django_request = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

    authenticated_user, claims = JWTCookieOrHeaderAuthentication().authenticate(
        _wrap(django_request)
    )

    assert authenticated_user == user
    assert claims["sub"] == str(user.pk)


@pytest.mark.django_db
def test_authenticate_resolves_user_from_cookie():
    user = UserFactory()
    token = TokenService().issue_access_token(user)
    django_request = RequestFactory().get("/")
    django_request.COOKIES["access_token"] = token

    authenticated_user, _ = JWTCookieOrHeaderAuthentication().authenticate(_wrap(django_request))

    assert authenticated_user == user


def test_authenticate_rejects_a_malformed_token():
    django_request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer not-a-real-jwt")

    with pytest.raises(exceptions.AuthenticationFailed):
        JWTCookieOrHeaderAuthentication().authenticate(_wrap(django_request))


@pytest.mark.django_db
def test_authenticate_rejects_a_token_for_a_now_inactive_user():
    user = UserFactory()
    token = TokenService().issue_access_token(user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    django_request = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {token}")

    with pytest.raises(exceptions.AuthenticationFailed):
        JWTCookieOrHeaderAuthentication().authenticate(_wrap(django_request))
