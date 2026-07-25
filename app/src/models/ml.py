from .email import EmailMessage
from .prediction import EmailPrediction


class SpamModel:
    """ML-модель для определения spam/ham."""

    def __init__(self, name: str, cost_per_email: int) -> None:
        self._name = name
        self._cost_per_email = cost_per_email

    def price_for(self, emails_count: int) -> int:
        return self._cost_per_email * emails_count

    def predict(self, emails: list[EmailMessage]) -> list[EmailPrediction]:
        ...
