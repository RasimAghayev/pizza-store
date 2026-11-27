import pytest

from apps.customers.repositories.customer_repository import CustomerRepository


@pytest.mark.django_db
def test_create_persists_a_customer():
    repository = CustomerRepository()

    customer = repository.create(user_id=42)

    assert customer.pk is not None
    assert customer.user_id == 42
    assert customer.consent_personal_data_at is None


@pytest.mark.django_db
def test_get_by_user_id_returns_none_when_not_found():
    repository = CustomerRepository()

    assert repository.get_by_user_id(999) is None
