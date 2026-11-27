import pytest
from django.core.cache import cache

from apps.customers.domain.otp import hash_otp_code
from apps.customers.services.profile_service import CustomerNotFoundError
from apps.customers.services.verification_service import (
    InvalidOtpError,
    PhoneNotOnFileError,
    VerificationService,
)
from apps.customers.tests.factories import CustomerFactory
from apps.identity.domain.rbac import RoleCode
from apps.identity.services.role_assignment_service import RoleAssignmentService
from apps.identity.tests.factories import UserFactory


class _RecordingNotificationGateway:
    def __init__(self) -> None:
        self.emails: list[tuple[str, str]] = []
        self.sms: list[tuple[str, str]] = []

    def send_email_otp(self, email: str, code: str) -> None:
        self.emails.append((email, code))

    def send_sms_otp(self, phone: str, code: str) -> None:
        self.sms.append((phone, code))


def _service(gateway: _RecordingNotificationGateway) -> VerificationService:
    return VerificationService(notification_gateway=gateway)


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_request_email_verification_stores_the_hashed_code_with_a_ttl():
    user = UserFactory()
    CustomerFactory(user_id=user.pk)
    gateway = _RecordingNotificationGateway()

    _service(gateway).request_email_verification(user.pk)

    assert len(gateway.emails) == 1
    sent_email, sent_code = gateway.emails[0]
    assert sent_email == user.email
    assert cache.get(f"otp:email_verify:{user.pk}") == hash_otp_code(sent_code)


@pytest.mark.django_db
def test_request_email_verification_raises_for_an_unknown_user():
    with pytest.raises(CustomerNotFoundError):
        _service(_RecordingNotificationGateway()).request_email_verification(999999)


@pytest.mark.django_db
def test_confirm_email_verification_with_the_right_code_succeeds_and_deletes_the_key():
    user = UserFactory()
    CustomerFactory(user_id=user.pk)
    gateway = _RecordingNotificationGateway()
    service = _service(gateway)
    service.request_email_verification(user.pk)
    _, code = gateway.emails[0]

    customer = service.confirm_email_verification(user.pk, code)

    assert customer.email_verified_at is not None
    assert cache.get(f"otp:email_verify:{user.pk}") is None


@pytest.mark.django_db
def test_confirm_email_verification_with_the_wrong_code_fails_without_deleting_the_key():
    user = UserFactory()
    CustomerFactory(user_id=user.pk)
    gateway = _RecordingNotificationGateway()
    service = _service(gateway)
    service.request_email_verification(user.pk)

    with pytest.raises(InvalidOtpError):
        service.confirm_email_verification(user.pk, "000000")

    assert cache.get(f"otp:email_verify:{user.pk}") is not None


@pytest.mark.django_db
def test_confirm_email_verification_after_the_key_has_expired_fails():
    user = UserFactory()
    CustomerFactory(user_id=user.pk)
    gateway = _RecordingNotificationGateway()
    service = _service(gateway)
    service.request_email_verification(user.pk)
    _, code = gateway.emails[0]
    cache.delete(f"otp:email_verify:{user.pk}")  # simulates TTL expiry

    with pytest.raises(InvalidOtpError):
        service.confirm_email_verification(user.pk, code)


@pytest.mark.django_db
def test_request_phone_verification_without_a_phone_on_file_raises():
    user = UserFactory()
    CustomerFactory(user_id=user.pk, phone=None)

    with pytest.raises(PhoneNotOnFileError):
        _service(_RecordingNotificationGateway()).request_phone_verification(user.pk)


@pytest.mark.django_db
def test_verifying_only_one_channel_does_not_grant_verified_customer():
    user = UserFactory()
    CustomerFactory(user_id=user.pk)
    gateway = _RecordingNotificationGateway()
    service = _service(gateway)
    service.request_email_verification(user.pk)
    _, code = gateway.emails[0]

    service.confirm_email_verification(user.pk, code)

    role_codes = {a.role_code for a in RoleAssignmentService().roles_for(user.pk)}
    assert RoleCode.VERIFIED_CUSTOMER not in role_codes


@pytest.mark.django_db
def test_verifying_both_channels_grants_verified_customer_exactly_once():
    user = UserFactory()
    CustomerFactory(user_id=user.pk, phone="555-0100")
    gateway = _RecordingNotificationGateway()
    service = _service(gateway)

    service.request_email_verification(user.pk)
    service.confirm_email_verification(user.pk, gateway.emails[-1][1])
    service.request_phone_verification(user.pk)
    service.confirm_phone_verification(user.pk, gateway.sms[-1][1])

    assignments = RoleAssignmentService().roles_for(user.pk)
    matching = [a for a in assignments if a.role_code == RoleCode.VERIFIED_CUSTOMER]
    assert len(matching) == 1
