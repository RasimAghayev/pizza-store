import datetime as dt

import pytest
from django.db import connection
from django.utils import timezone

from apps.customers.models.address import Address
from apps.customers.models.customer import Customer
from apps.customers.tests.factories import AddressFactory, CustomerFactory


@pytest.mark.django_db
def test_phone_and_date_of_birth_are_stored_encrypted_at_rest():
    customer = CustomerFactory(consent_personal_data_at=timezone.now())
    customer.phone = "+1-202-555-0143"
    customer.date_of_birth = dt.date(1990, 5, 17)
    customer.save(update_fields=["phone", "date_of_birth"])

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT phone, date_of_birth FROM customers_customer WHERE id = %s", [customer.pk]
        )
        raw_phone, raw_date_of_birth = cursor.fetchone()

    assert raw_phone != "+1-202-555-0143"
    assert raw_date_of_birth != "1990-05-17"

    reloaded = Customer.objects.get(pk=customer.pk)
    assert reloaded.phone == "+1-202-555-0143"
    assert reloaded.date_of_birth == dt.date(1990, 5, 17)


@pytest.mark.django_db
def test_address_street_and_unit_is_stored_encrypted_at_rest():
    address = AddressFactory(street_and_unit="742 Evergreen Terrace, Apt 2")

    with connection.cursor() as cursor:
        cursor.execute("SELECT street_and_unit FROM customers_address WHERE id = %s", [address.pk])
        (raw_street,) = cursor.fetchone()

    assert raw_street != "742 Evergreen Terrace, Apt 2"

    reloaded = Address.objects.get(pk=address.pk)
    assert reloaded.street_and_unit == "742 Evergreen Terrace, Apt 2"
