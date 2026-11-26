import datetime as dt

from django.utils import timezone

from apps.identity.models import RefreshToken, User


class RefreshTokenRepository:
    """Only file in this module allowed to issue an ORM query, per ADR 0004."""

    def create(
        self,
        *,
        user: User,
        token_hash: str,
        issued_at: dt.datetime,
        expires_at: dt.datetime,
        device_label: str = "",
        ip_address: str | None = None,
    ) -> RefreshToken:
        return RefreshToken.objects.create(
            user=user,
            token_hash=token_hash,
            issued_at=issued_at,
            expires_at=expires_at,
            device_label=device_label,
            ip_address=ip_address,
        )

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return RefreshToken.objects.filter(token_hash=token_hash).select_related("user").first()

    def mark_replaced(self, old: RefreshToken, new: RefreshToken) -> None:
        old.replaced_by = new
        old.save(update_fields=["replaced_by"])

    def revoke(self, record: RefreshToken) -> None:
        record.revoked_at = timezone.now()
        record.save(update_fields=["revoked_at"])

    def revoke_family(self, record: RefreshToken) -> None:
        """Walks `replaced_by` both directions from `record` (ADR 0006's stolen-token
        signal) and revokes every row in the chain that is not already revoked."""
        now = timezone.now()
        for node in self._family(record):
            if node.revoked_at is None:
                node.revoked_at = now
                node.save(update_fields=["revoked_at"])

    def _family(self, record: RefreshToken) -> list[RefreshToken]:
        chain = {record.pk: record}

        node = record
        while node.replaced_by_id is not None:
            node = node.replaced_by
            chain[node.pk] = node

        node = record
        predecessor = node.replaces.first()
        while predecessor is not None:
            chain[predecessor.pk] = predecessor
            predecessor = predecessor.replaces.first()

        return list(chain.values())
