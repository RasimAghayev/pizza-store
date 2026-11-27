from apps.identity.domain.email import Email
from apps.identity.models import User
from apps.identity.repositories.user_repository import UserRepository


class EmailAlreadyRegisteredError(Exception):
    pass


class RegistrationService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self._user_repository = user_repository or UserRepository()

    def register(self, *, email: str, password: str) -> User:
        validated_email = Email(email)
        if self._user_repository.get_by_email(validated_email.value) is not None:
            raise EmailAlreadyRegisteredError(validated_email.value)
        return self._user_repository.create(email=validated_email.value, password=password)
