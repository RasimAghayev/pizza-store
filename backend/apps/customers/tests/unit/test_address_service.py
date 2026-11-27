import pytest

from apps.customers.models.address import Address
from apps.customers.services.address_service import AddressNotFoundError, AddressService
from apps.customers.services.profile_service import CustomerNotFoundError
from apps.customers.tests.factories import AddressFactory, CustomerFactory


@pytest.mark.django_db
def test_create_defaults_to_not_default():
    customer = CustomerFactory()

    address = AddressService().create(
        user_id=customer.user_id, street_and_unit="1 Pine St", city="Springfield"
    )

    assert address.is_default is False


@pytest.mark.django_db
def test_creating_a_second_default_address_clears_the_first():
    customer = CustomerFactory()
    first = AddressFactory(customer=customer, is_default=True)

    second = AddressService().create(
        user_id=customer.user_id,
        street_and_unit="2 Oak St",
        city="Springfield",
        is_default=True,
    )

    first.refresh_from_db()
    assert first.is_default is False
    assert second.is_default is True
    assert Address.objects.filter(customer=customer, is_default=True).count() == 1


@pytest.mark.django_db
def test_setting_default_on_update_clears_every_other_default():
    customer = CustomerFactory()
    first = AddressFactory(customer=customer, is_default=True)
    second = AddressFactory(customer=customer, is_default=False)

    AddressService().update(user_id=customer.user_id, address_id=second.pk, is_default=True)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_default is False
    assert second.is_default is True


@pytest.mark.django_db
def test_get_owned_raises_not_found_for_another_customers_address():
    owner = CustomerFactory()
    other = CustomerFactory()
    address = AddressFactory(customer=owner)

    with pytest.raises(AddressNotFoundError):
        AddressService().get_owned(user_id=other.user_id, address_id=address.pk)


@pytest.mark.django_db
def test_delete_removes_the_row():
    customer = CustomerFactory()
    address = AddressFactory(customer=customer)

    AddressService().delete(user_id=customer.user_id, address_id=address.pk)

    assert not Address.objects.filter(pk=address.pk).exists()


@pytest.mark.django_db
def test_create_raises_customer_not_found_for_an_unknown_user():
    with pytest.raises(CustomerNotFoundError):
        AddressService().create(user_id=999999, street_and_unit="1 Pine St", city="Springfield")
