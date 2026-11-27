from django.db import models

from shared.encryption.fields import EncryptedCharField, EncryptedDateField


class Customer(models.Model):
    """One row per registered customer (Issue #176). `user_id` is a plain field referencing
    `identity.User`'s primary key, not a Django ForeignKey -- `customers` must never import
    `identity.models`/`repositories`, per ADR 0004's cross-module import restriction; the
    only sanctioned call into `identity` is its `services/` entry point (see
    apps/customers/services/registration_service.py). `phone`/`date_of_birth` are
    Fernet-encrypted at rest (ADR 0006, Issue #179); `date_of_birth` additionally requires
    `consent_personal_data_at` to be set first -- enforced in
    services/profile_service.py::ProfileService.update_profile, not at this model layer."""

    user_id = models.PositiveBigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    consent_personal_data_at = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=100, blank=True, default="")
    last_name = models.CharField(max_length=100, blank=True, default="")
    phone = EncryptedCharField(null=True, blank=True)
    date_of_birth = EncryptedDateField(null=True, blank=True)
    # Set by services/verification_service.py::VerificationService on a successful OTP
    # confirmation (Issue #177) -- plaintext timestamps, not encrypted: a verification time
    # carries none of the sensitivity that justifies phone/date_of_birth's encryption.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "customers"

    def __str__(self) -> str:
        return f"Customer(user_id={self.user_id})"
