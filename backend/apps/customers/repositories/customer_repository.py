from apps.customers.models.customer import Customer


class CustomerRepository:
    """Only file in this module allowed to issue an ORM query for Customer, per ADR 0004."""

    def create(self, *, user_id: int) -> Customer:
        return Customer.objects.create(user_id=user_id)

    def get_by_user_id(self, user_id: int) -> Customer | None:
        return Customer.objects.filter(user_id=user_id).first()

    def update(self, customer: Customer, **fields: object) -> Customer:
        for field, value in fields.items():
            setattr(customer, field, value)
        customer.save(update_fields=list(fields))
        return customer
