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
