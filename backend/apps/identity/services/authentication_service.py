from apps.identity.models import User
from apps.identity.repositories.user_repository import UserRepository


class AuthenticationService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self._user_repository = user_repository or UserRepository()

    def verify_credentials(self, email: str, raw_password: str) -> User | None:
        user = self._user_repository.get_by_email(email)
        if user is None:
            return None
        if not user.check_password(raw_password):
            return None
        return user
