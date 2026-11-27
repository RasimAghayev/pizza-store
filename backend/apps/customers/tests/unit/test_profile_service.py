import datetime as dt

import pytest
from django.utils import timezone

from apps.customers.services.profile_service import (
    ConsentRequiredError,
    CustomerNotFoundError,
    ProfileService,
)
from apps.customers.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_update_profile_sets_only_the_provided_fields():
    customer = CustomerFactory(first_name="Jane", last_name="Doe")

    updated = ProfileService().update_profile(customer.user_id, last_name="Smith")

    assert updated.first_name == "Jane"
    assert updated.last_name == "Smith"


@pytest.mark.django_db
def test_update_profile_rejects_date_of_birth_without_prior_consent():
    customer = CustomerFactory(consent_personal_data_at=None)

    with pytest.raises(ConsentRequiredError):
        ProfileService().update_profile(customer.user_id, date_of_birth=dt.date(1990, 5, 17))


@pytest.mark.django_db
def test_update_profile_allows_date_of_birth_once_consent_is_recorded():
    customer = CustomerFactory(consent_personal_data_at=timezone.now())

    updated = ProfileService().update_profile(customer.user_id, date_of_birth=dt.date(1990, 5, 17))

    assert updated.date_of_birth == dt.date(1990, 5, 17)


@pytest.mark.django_db
def test_record_consent_sets_the_timestamp():
    customer = CustomerFactory(consent_personal_data_at=None)

    updated = ProfileService().record_consent(customer.user_id)

    assert updated.consent_personal_data_at is not None


@pytest.mark.django_db
def test_get_profile_raises_not_found_for_an_unknown_user_id():
    with pytest.raises(CustomerNotFoundError):
        ProfileService().get_profile(999999)
