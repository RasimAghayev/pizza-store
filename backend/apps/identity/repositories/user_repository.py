from apps.identity.models import User


class UserRepository:
    """Only file in this module allowed to issue an ORM query, per ADR 0004."""

    def create(self, *, email: str, password: str) -> User:
        return User.objects.create_user(email=email, password=password)

    def get_by_email(self, email: str) -> User | None:
        return User.objects.filter(email__iexact=email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return User.objects.filter(pk=user_id, is_active=True).first()

    def set_password(self, user: User, new_password: str) -> None:
        user.set_password(new_password)
        user.save(update_fields=["password"])
