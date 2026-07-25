from datetime import datetime

from .email import EmailMessage, ValidationError
from .enums import EmailLabel, PredictionStatus


class EmailPrediction:
    """Результат проверки письма."""

    def __init__(self, email: EmailMessage, label: EmailLabel, probability: float) -> None:
        self._email = email
        self._label = label
        self._probability = probability


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
