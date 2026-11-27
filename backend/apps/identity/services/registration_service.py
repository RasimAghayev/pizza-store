from apps.identity.domain.email import Email
from apps.identity.models import User
from apps.identity.repositories.user_repository import UserRepository


class RegistrationService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self._user_repository = user_repository or UserRepository()

    def register(self, *, email: str, password: str) -> User:
        validated_email = Email(email)
        return self._user_repository.create(email=validated_email.value, password=password)
