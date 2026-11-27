import json

import pytest
from faker import Faker

from apps.customers.models.customer import Customer
from apps.identity.models import User

fake = Faker()

REGISTER_URL = "/api/v1/customers/register/"


def _post(client, payload):
    return client.post(REGISTER_URL, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_register_returns_201_with_the_new_customers_id(client):
    email = fake.email()

    response = _post(client, {"email": email, "password": fake.password()})

    assert response.status_code == 201
    body = response.json()
    customer = Customer.objects.get(pk=body["id"])
    assert customer.user_id == User.objects.get(email=email.strip().lower()).pk


@pytest.mark.django_db
def test_register_rejects_a_duplicate_email(client):
    email = fake.email()
    _post(client, {"email": email, "password": fake.password()})

    response = _post(client, {"email": email, "password": fake.password()})

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "email" in body["error"]["details"]


@pytest.mark.django_db
def test_register_rejects_an_unknown_field(client):
    response = _post(client, {"email": fake.email(), "password": fake.password(), "is_admin": True})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_register_rejects_a_missing_password(client):
    response = _post(client, {"email": fake.email()})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
