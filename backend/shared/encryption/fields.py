"""Fernet-based field-level encryption (ADR 0006 "Encryption at rest", Issue #179).

A thin custom field was chosen over `django-cryptography` after checking its current state
(research-before-implementing): its latest PyPI release predates Django 6 support and its
last commit is years old, so it is not a safe new dependency for this stack -- a small field
built on the `cryptography` dependency already used by apps/identity/services/token_service.py
satisfies the requirement just as well with a smaller footprint.
"""

from __future__ import annotations

import datetime as dt

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


def _load_or_generate_key() -> bytes:
    raw = settings.FIELD_ENCRYPTION_KEY
    if raw:
        try:
            Fernet(raw.encode())
        except ValueError:
            # The mounted secret isn't a valid Fernet key -- e.g. the tracked
            # field_encryption_key.txt.example placeholder, copied in by CI workflows that
            # don't run scripts/generate-field-encryption-key.py (see
            # docs/security/secret-management.md). Same fallback shape as
            # apps/identity/services/token_service.py's JWT keypair loader.
            pass
        else:
            return raw.encode()
    # No usable `field_encryption_key` Compose secret -- generate a process-local key so
    # encrypt/decrypt still round-trips within this process. Never persisted; a restart makes
    # every previously-encrypted row unreadable under this key, which is fine for a
    # throwaway/test process but would be a real incident in any persistent environment.
    return Fernet.generate_key()


_FERNET = Fernet(_load_or_generate_key())


class EncryptedCharField(models.TextField):
    """Stores ciphertext in a TextField rather than a CharField -- Fernet's output (base64 of
    version + timestamp + IV + ciphertext + HMAC) is longer than the plaintext and not
    fixed-width, so a column `max_length` would be meaningless."""

    def get_prep_value(self, value):
        if value is None:
            return None
        return _FERNET.encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return _FERNET.decrypt(value.encode()).decode()


class EncryptedDateField(EncryptedCharField):
    """Same ciphertext-in-TextField storage as `EncryptedCharField`, round-tripping the
    plaintext through ISO 8601 (`date.isoformat()` / `date.fromisoformat()`) either side of
    encryption."""

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, dt.date):
            value = value.isoformat()
        return super().get_prep_value(value)

    def from_db_value(self, value, expression, connection):
        plaintext = super().from_db_value(value, expression, connection)
        if plaintext is None:
            return None
        return dt.date.fromisoformat(plaintext)
