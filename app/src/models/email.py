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
