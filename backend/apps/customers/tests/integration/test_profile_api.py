import json
from typing import cast

import pytest

from apps.customers.tests.factories import CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

PROFILE_URL = "/api/v1/customers/me/profile/"
CONSENT_URL = "/api/v1/customers/me/profile/consent/"


def _authenticated(client):
    user = cast(User, UserFactory())
    customer = CustomerFactory(user_id=user.pk)
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return customer


def _patch_json(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_anonymous_request_is_rejected(client):
    response = client.get(PROFILE_URL)

    assert response.status_code == 401


@pytest.mark.django_db
def test_get_profile_returns_the_current_customers_row(client):
    customer = _authenticated(client)
    customer.first_name = "Jane"
    customer.save(update_fields=["first_name"])

    response = client.get(PROFILE_URL)

    assert response.status_code == 200
    assert response.json()["first_name"] == "Jane"


@pytest.mark.django_db
def test_patch_updates_name_and_phone(client):
    _authenticated(client)

    response = _patch_json(
        client, PROFILE_URL, {"first_name": "Homer", "last_name": "Simpson", "phone": "555-0100"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Homer"
    assert body["last_name"] == "Simpson"
    assert body["phone"] == "555-0100"


@pytest.mark.django_db
def test_patch_rejects_date_of_birth_before_consent_is_recorded(client):
    _authenticated(client)

    response = _patch_json(client, PROFILE_URL, {"date_of_birth": "1990-05-17"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "date_of_birth" in response.json()["error"]["details"]


@pytest.mark.django_db
def test_consent_then_date_of_birth_succeeds(client):
    _authenticated(client)

    consent_response = client.post(CONSENT_URL)
    assert consent_response.status_code == 200
    assert consent_response.json()["consent_personal_data_at"] is not None

    response = _patch_json(client, PROFILE_URL, {"date_of_birth": "1990-05-17"})

    assert response.status_code == 200
    assert response.json()["date_of_birth"] == "1990-05-17"


@pytest.mark.django_db
def test_patch_rejects_an_unknown_field(client):
    _authenticated(client)

    response = _patch_json(client, PROFILE_URL, {"is_admin": True})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
