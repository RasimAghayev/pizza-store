import uuid
from dataclasses import asdict

from django.db import transaction
from django.utils import timezone

from apps.customers.events.customer_registered import (
    EVENT_TYPE,
    SCHEMA_VERSION,
    CustomerRegisteredPayload,
)
from apps.customers.models.customer import Customer
from apps.customers.models.customer_outbox_event import CustomerOutboxEvent
from apps.customers.repositories.customer_repository import CustomerRepository
from apps.identity.domain.rbac import RoleCode

# calls identity.services.registration_service.RegistrationService.register() -- see
# backend/apps/identity/README.md's "inbound calls" section. identity.User/credential
# creation is identity's exclusive domain (ADR 0004); customers never constructs an
# identity.User row itself or imports identity.models/repositories.
from apps.identity.services.registration_service import (
    EmailAlreadyRegisteredError,
)
from apps.identity.services.registration_service import (
    RegistrationService as IdentityRegistrationService,
)
from apps.identity.services.role_assignment_service import RoleAssignmentService

__all__ = ["EmailAlreadyRegisteredError", "RegistrationService"]


class RegistrationService:
    def __init__(
        self,
        *,
        customer_repository: CustomerRepository | None = None,
        identity_registration_service: IdentityRegistrationService | None = None,
        role_assignment_service: RoleAssignmentService | None = None,
    ) -> None:
        self._customer_repository = customer_repository or CustomerRepository()
        self._identity_registration_service = (
            identity_registration_service or IdentityRegistrationService()
        )
        self._role_assignment_service = role_assignment_service or RoleAssignmentService()

    def register(self, *, email: str, password: str) -> Customer:
        with transaction.atomic():
            user = self._identity_registration_service.register(email=email, password=password)
            return self._provision_customer(user)

    def provision_customer(self, user) -> Customer:
        """Creates the Customer profile, assigns the `customer` role, and publishes
        CustomerRegistered for an identity.User that already exists -- the second half of
        register() above, factored out so
        apps.identity.services.social_login_service.SocialLoginService (Issue #178) can reuse
        it for a social-login-created User on its first-ever login, without duplicating this
        module's own create-Customer/assign-role/publish-event logic. Idempotent: a second
        call for a user who already has a Customer row returns the existing row and performs
        no further writes -- SocialLoginService calls this unconditionally on every login
        rather than pre-checking, since "does a Customer already exist" is exactly this
        method's own job to decide, not a judgment call to duplicate in every caller."""
        with transaction.atomic():
            existing = self._customer_repository.get_by_user_id(user.pk)
            if existing is not None:
                return existing
            return self._provision_customer(user)

    def _provision_customer(self, user) -> Customer:
        customer = self._customer_repository.create(user_id=user.pk)
        self._role_assignment_service.assign(user=user, role_code=RoleCode.CUSTOMER)
        self._publish_customer_registered(customer, email=user.email)
        return customer

    def _publish_customer_registered(self, customer: Customer, *, email: str) -> None:
        payload = CustomerRegisteredPayload(
            user_id=customer.user_id, email=email, registered_at=timezone.now().isoformat()
        )
        CustomerOutboxEvent.objects.create(
            aggregate_type="customer",
            aggregate_id=str(customer.user_id),
            event_type=EVENT_TYPE,
            schema_version=SCHEMA_VERSION,
            payload=asdict(payload),
            correlation_id=uuid.uuid4(),
        )
