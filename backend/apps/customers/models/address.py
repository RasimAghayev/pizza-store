from django.db import models

from apps.customers.models.customer import Customer
from shared.encryption.fields import EncryptedCharField


class Address(models.Model):
    """A customer's saved delivery address (Issue #179). `street_and_unit` is the only
    Fernet-encrypted column (ADR 0006) -- `city`/`postal_code` stay plaintext since
    branch-matching queries need them and neither is sensitive on its own.
    `latitude`/`longitude` are nullable: master prompt section 11 requires a
    manually-entered/map-picked address with no GPS coordinates to be just as valid as a
    GPS-derived one -- location permission is never mandatory."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, blank=True, default="")
    street_and_unit = EncryptedCharField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "customers"

    def __str__(self) -> str:
        return f"Address(id={self.pk}, customer_id={self.customer_id})"
