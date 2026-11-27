from django.core.cache import cache
from django.utils import timezone

from apps.customers.domain.otp import OTP_TTL_SECONDS, generate_otp_code, hash_otp_code
from apps.customers.models.customer import Customer
from apps.customers.repositories.customer_repository import CustomerRepository
from apps.customers.services.notification_gateway import (
    LoggingNotificationGateway,
    NotificationGateway,
)
from apps.customers.services.profile_service import CustomerNotFoundError

# calls identity.services.{user_lookup_service,role_assignment_service} -- see
# backend/apps/identity/README.md's "inbound calls" section. customers never imports
# identity.models/repositories directly, per ADR 0004.
from apps.identity.domain.rbac import RoleCode
from apps.identity.services.role_assignment_service import RoleAssignmentService
from apps.identity.services.user_lookup_service import UserLookupService

__all__ = ["CustomerNotFoundError", "InvalidOtpError", "PhoneNotOnFileError", "VerificationService"]


class InvalidOtpError(Exception):
    """Raised for a missing, expired, or mismatched OTP code."""


class PhoneNotOnFileError(Exception):
    """Raised when phone verification is requested before a phone number has been saved to
    the customer's profile -- there is nothing to send an SMS code to."""


def _otp_cache_key(purpose: str, user_id: int) -> str:
    return f"otp:{purpose}:{user_id}"


class VerificationService:
    """Email/phone OTP verification (Issue #177). Redis's TTL is the enforcement mechanism
    for OTP expiry, not just an optimization (docs/database/redis-caching-and-ttl-policy.md);
    only a SHA-256 hash of the code is ever stored, same rationale as
    apps/identity/services/token_service.py's refresh-token hashing. A customer becomes
    `verified_customer` only once BOTH channels are verified (Issue #177's own Implementation
    Prompt), tracked via two nullable `Customer` columns."""

    def __init__(
        self,
        *,
        customer_repository: CustomerRepository | None = None,
        user_lookup_service: UserLookupService | None = None,
        role_assignment_service: RoleAssignmentService | None = None,
        notification_gateway: NotificationGateway | None = None,
    ) -> None:
        self._customer_repository = customer_repository or CustomerRepository()
        self._user_lookup_service = user_lookup_service or UserLookupService()
        self._role_assignment_service = role_assignment_service or RoleAssignmentService()
        self._notification_gateway = notification_gateway or LoggingNotificationGateway()

    def request_email_verification(self, user_id: int) -> None:
        self._customer(user_id)
        user = self._user_lookup_service.get_by_id(user_id)
        code = self._issue_code("email_verify", user_id)
        self._notification_gateway.send_email_otp(user.email, code)

    def confirm_email_verification(self, user_id: int, code: str) -> Customer:
        self._confirm_code("email_verify", user_id, code)
        customer = self._customer_repository.update(
            self._customer(user_id), email_verified_at=timezone.now()
        )
        self._maybe_upgrade_to_verified_customer(customer)
        return customer

    def request_phone_verification(self, user_id: int) -> None:
        customer = self._customer(user_id)
        if not customer.phone:
            raise PhoneNotOnFileError(user_id)
        code = self._issue_code("phone_verify", user_id)
        self._notification_gateway.send_sms_otp(customer.phone, code)

    def confirm_phone_verification(self, user_id: int, code: str) -> Customer:
        self._confirm_code("phone_verify", user_id, code)
        customer = self._customer_repository.update(
            self._customer(user_id), phone_verified_at=timezone.now()
        )
        self._maybe_upgrade_to_verified_customer(customer)
        return customer

    def _customer(self, user_id: int) -> Customer:
        customer = self._customer_repository.get_by_user_id(user_id)
        if customer is None:
            raise CustomerNotFoundError(user_id)
        return customer

    def _issue_code(self, purpose: str, user_id: int) -> str:
        code = generate_otp_code()
        cache.set(_otp_cache_key(purpose, user_id), hash_otp_code(code), timeout=OTP_TTL_SECONDS)
        return code

    def _confirm_code(self, purpose: str, user_id: int, code: str) -> None:
        key = _otp_cache_key(purpose, user_id)
        stored_hash = cache.get(key)
        if stored_hash is None or stored_hash != hash_otp_code(code):
            raise InvalidOtpError("Invalid or expired verification code.")
        # Single-use even within the TTL window (Issue #177 Security Requirements) -- the
        # explicit delete and the TTL are both required, not either alone.
        cache.delete(key)

    def _maybe_upgrade_to_verified_customer(self, customer: Customer) -> None:
        if not (customer.email_verified_at and customer.phone_verified_at):
            return
        already_verified = any(
            assignment.role_code == RoleCode.VERIFIED_CUSTOMER
            for assignment in self._role_assignment_service.roles_for(customer.user_id)
        )
        if already_verified:
            return
        user = self._user_lookup_service.get_by_id(customer.user_id)
        self._role_assignment_service.assign(user=user, role_code=RoleCode.VERIFIED_CUSTOMER)
