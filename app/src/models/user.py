from .enums import UserRole


class User:
    """Пользователь сервиса."""

    def __init__(self, email: str, password_hash: str, role: UserRole) -> None:
        self._email = email
        self.__password_hash = password_hash
        self._role = role

    @property
    def email(self) -> str:
        return self._email

    def check_password(self, password: str) -> bool:
        ...
