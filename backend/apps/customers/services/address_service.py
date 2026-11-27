from django.db import transaction

from apps.customers.models.address import Address
from apps.customers.models.customer import Customer
from apps.customers.repositories.address_repository import AddressRepository
from apps.customers.repositories.customer_repository import CustomerRepository
from apps.customers.services.profile_service import CustomerNotFoundError


class AddressNotFoundError(Exception):
    """Raised for an address id that doesn't exist, or exists but isn't owned by the
    requesting customer -- the view maps both cases to the same 404, never a 403, so an
    unauthorized request can't distinguish "not yours" from "doesn't exist" (Issue #179
    Security Requirements)."""


class AddressService:
    def __init__(
        self,
        *,
        address_repository: AddressRepository | None = None,
        customer_repository: CustomerRepository | None = None,
    ) -> None:
        self._address_repository = address_repository or AddressRepository()
        self._customer_repository = customer_repository or CustomerRepository()

    def list_for_customer(self, user_id: int) -> list[Address]:
        customer = self._customer(user_id)
        return self._address_repository.list_for_customer(customer.pk)

    def get_owned(self, *, user_id: int, address_id: int) -> Address:
        customer = self._customer(user_id)
        address = self._address_repository.get_for_customer(address_id, customer.pk)
        if address is None:
            raise AddressNotFoundError(address_id)
        return address

    def get_owned_by_customer_id(self, *, customer_id: int, address_id: int) -> Address | None:
        """Cross-module lookup for a caller that already resolved `customer_id` (=
        `Customer.pk`) itself and has no `user_id` to go through `get_owned()`/`_customer()`
        -- e.g. `apps.orders.services.order_service.OrderService.checkout()` (Issue #197),
        which gets `customer_id` from its own view's `_customer_id_for(request)`. Returns
        `None` rather than raising `AddressNotFoundError` on any mismatch: the non-raising,
        cross-module convention `BranchService.get_by_id()`/`ProfileService.get_by_id()`
        already use, letting the calling module raise its own locally-named not-found error
        (ADR 0004 -- orders never imports this module's exception types)."""
        return self._address_repository.get_for_customer(address_id, customer_id)

    def create(self, *, user_id: int, is_default: bool = False, **fields: object) -> Address:
        customer = self._customer(user_id)
        with transaction.atomic():
            if is_default:
                self._address_repository.clear_default_for_customer(customer.pk)
            return self._address_repository.create(
                customer_id=customer.pk, is_default=is_default, **fields
            )

    def update(self, *, user_id: int, address_id: int, **fields: object) -> Address:
        address = self.get_owned(user_id=user_id, address_id=address_id)
        with transaction.atomic():
            if fields.get("is_default"):
                self._address_repository.clear_default_for_customer(
                    address.customer_id, exclude_id=address.pk
                )
            return self._address_repository.update(address, **fields)

    def delete(self, *, user_id: int, address_id: int) -> None:
        address = self.get_owned(user_id=user_id, address_id=address_id)
        self._address_repository.delete(address)

    def _customer(self, user_id: int) -> Customer:
        customer = self._customer_repository.get_by_user_id(user_id)
        if customer is None:
            raise CustomerNotFoundError(user_id)
        return customer
