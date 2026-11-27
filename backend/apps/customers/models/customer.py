from django.db import models


class Customer(models.Model):
    """One row per registered customer (Issue #176). `user_id` is a plain field referencing
    `identity.User`'s primary key, not a Django ForeignKey -- `customers` must never import
    `identity.models`/`repositories`, per ADR 0004's cross-module import restriction; the
    only sanctioned call into `identity` is its `services/` entry point (see
    apps/customers/services/registration_service.py). Profile fields (name/phone/DOB) and
    saved addresses are Issue #179's job, not this one."""

    user_id = models.PositiveBigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    consent_personal_data_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "customers"

    def __str__(self) -> str:
        return f"Customer(user_id={self.user_id})"
