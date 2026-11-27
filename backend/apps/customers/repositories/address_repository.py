from apps.customers.models.address import Address


class AddressRepository:
    """Only file in this module allowed to issue an ORM query for Address, per ADR 0004."""

    def create(self, *, customer_id: int, **fields: object) -> Address:
        return Address.objects.create(customer_id=customer_id, **fields)

    def get_for_customer(self, address_id: int, customer_id: int) -> Address | None:
        return Address.objects.filter(pk=address_id, customer_id=customer_id).first()

    def list_for_customer(self, customer_id: int) -> list[Address]:
        return list(Address.objects.filter(customer_id=customer_id).order_by("-is_default", "id"))

    def update(self, address: Address, **fields: object) -> Address:
        for field, value in fields.items():
            setattr(address, field, value)
        address.save(update_fields=list(fields))
        return address

    def delete(self, address: Address) -> None:
        address.delete()

    def clear_default_for_customer(
        self, customer_id: int, *, exclude_id: int | None = None
    ) -> None:
        """Enforces "exactly one default address per customer" at the service layer (Issue
        #179) by clearing every other default before a new one is set -- called inside the
        same transaction as the write that sets the new default."""
        queryset = Address.objects.filter(customer_id=customer_id, is_default=True)
        if exclude_id is not None:
            queryset = queryset.exclude(pk=exclude_id)
        queryset.update(is_default=False)
