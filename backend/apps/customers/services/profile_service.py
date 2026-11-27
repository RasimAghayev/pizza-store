from django.utils import timezone

from apps.customers.models.customer import Customer
from apps.customers.repositories.customer_repository import CustomerRepository


class CustomerNotFoundError(Exception):
    """Raised when no Customer row exists for the given identity.User id."""


class ConsentRequiredError(Exception):
    """Raised when a profile update tries to set `date_of_birth` before
    `Customer.consent_personal_data_at` has been recorded (Issue #179 Security
    Requirements) -- DOB is personal data that specifically requires consent first, per
    Epic #14's Security Requirements."""


class ProfileService:
    def __init__(self, *, customer_repository: CustomerRepository | None = None) -> None:
        self._customer_repository = customer_repository or CustomerRepository()

    def get_profile(self, user_id: int) -> Customer:
        customer = self._customer_repository.get_by_user_id(user_id)
        if customer is None:
            raise CustomerNotFoundError(user_id)
        return customer

    def get_by_id(self, customer_id: int) -> Customer | None:
        """Cross-module entry point keyed by `Customer.pk` itself (unlike `get_profile`,
        keyed by `identity.User.pk`) -- called by `apps.cart.services.cart_service
        .CartService.get_or_create_cart` to validate a `customer_id` exists once, at cart
        creation only (see `backend/apps/cart/README.md`); `cart` never imports
        `apps.customers.models`/`repositories` directly (ADR 0004)."""
        return self._customer_repository.get_by_id(customer_id)

    def update_profile(self, user_id: int, **fields: object) -> Customer:
        customer = self.get_profile(user_id)
        if "date_of_birth" in fields and fields["date_of_birth"] is not None:
            if customer.consent_personal_data_at is None:
                raise ConsentRequiredError(user_id)
        return self._customer_repository.update(customer, **fields)

    def record_consent(self, user_id: int) -> Customer:
        customer = self.get_profile(user_id)
        return self._customer_repository.update(customer, consent_personal_data_at=timezone.now())
