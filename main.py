from datetime import datetime
from enum import Enum


class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"


class PredictionStatus(Enum):
    CREATED = "created"
    DONE = "done"
    FAILED = "failed"


class EmailLabel(Enum):
    SPAM = "spam"
    HAM = "ham"


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


class CreditBalance:
    """Кредитный баланс пользователя."""

    def __init__(self, user_email: str, amount: int = 0) -> None:
        self._user_email = user_email
        self.__amount = amount

    @property
    def amount(self) -> int:
        return self.__amount

    def can_pay(self, amount: int) -> bool:
        return self.__amount >= amount

    def top_up(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self.__amount += amount

    def charge(self, amount: int) -> None:
        if not self.can_pay(amount):
            raise ValueError("Недостаточно средств")
        self.__amount -= amount


class EmailMessage:
    """Письмо для проверки."""

    def __init__(self, subject: str, body: str) -> None:
        self._subject = subject
        self._body = body

    def is_valid(self) -> bool:
        return bool(self._body.strip())

    def text_for_model(self) -> str:
        return f"{self._subject}\n{self._body}"


class ValidationError:
    """Ошибка во входных данных."""

    def __init__(self, row: int, field: str, message: str) -> None:
        self._row = row
        self._field = field
        self._message = message


class EmailValidator:
    """Проверяет загруженные письма."""

    def validate(
        self,
        emails: list[EmailMessage],
    ) -> tuple[list[EmailMessage], list[ValidationError]]:
        valid = []
        errors = []

        for row, email in enumerate(emails):
            if email.is_valid():
                valid.append(email)
            else:
                errors.append(ValidationError(row, "body", "Пустое тело письма"))

        return valid, errors


class EmailPrediction:
    """Результат проверки письма."""

    def __init__(self, email: EmailMessage, label: EmailLabel, probability: float) -> None:
        self._email = email
        self._label = label
        self._probability = probability


class SpamModel:
    """ML-модель для определения spam/ham."""

    def __init__(self, name: str, cost_per_email: int) -> None:
        self._name = name
        self._cost_per_email = cost_per_email

    def price_for(self, emails_count: int) -> int:
        return self._cost_per_email * emails_count

    def predict(self, emails: list[EmailMessage]) -> list[EmailPrediction]:
        ...


class PredictionRequest:
    """Задача на проверку писем."""

    def __init__(
        self,
        user_email: str,
        model_name: str,
        emails: list[EmailMessage],
        created_at: datetime,
    ) -> None:
        self._user_email = user_email
        self._model_name = model_name
        self._emails = emails
        self._created_at = created_at
        self._status = PredictionStatus.CREATED
        self._predictions: list[EmailPrediction] = []
        self._errors: list[ValidationError] = []
        self._charged = 0

    def complete(
        self,
        predictions: list[EmailPrediction],
        errors: list[ValidationError],
        charged: int,
    ) -> None:
        self._predictions = predictions
        self._errors = errors
        self._charged = charged
        self._status = PredictionStatus.DONE

    def fail(self, errors: list[ValidationError]) -> None:
        self._errors = errors
        self._status = PredictionStatus.FAILED


class Transaction:
    """Операция с балансом."""

    def __init__(self, user_email: str, amount: int, created_at: datetime) -> None:
        self._user_email = user_email
        self._amount = amount
        self._created_at = created_at

    def apply(self, balance: CreditBalance) -> None:
        ...


class TopUp(Transaction):
    """Пополнение баланса."""

    def apply(self, balance: CreditBalance) -> None:
        balance.top_up(self._amount)


class Charge(Transaction):
    """Списание за проверку."""

    def apply(self, balance: CreditBalance) -> None:
        balance.charge(self._amount)
