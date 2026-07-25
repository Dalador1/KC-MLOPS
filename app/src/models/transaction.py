from datetime import datetime

from .balance import CreditBalance


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
