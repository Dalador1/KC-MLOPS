from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.enums import EmailLabel, PredictionStatus, UserRole
from .orm import (
    CreditBalanceORM,
    EmailPredictionORM,
    PredictionRequestORM,
    SpamModelORM,
    TransactionORM,
    UserORM,
    ValidationErrorORM,
)


def create_user(
    session: Session,
    email: str,
    password_hash: str,
    role: UserRole = UserRole.USER,
    initial_balance: int = 0,
) -> UserORM:
    existing_user = session.scalar(select(UserORM).where(UserORM.email == email))
    if existing_user is not None:
        return existing_user

    user = UserORM(email=email, password_hash=password_hash, role=role.value)
    user.balance = CreditBalanceORM(amount=initial_balance)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user(session: Session, email: str) -> UserORM | None:
    return session.scalar(select(UserORM).where(UserORM.email == email))


def create_spam_model(session: Session, name: str, cost_per_email: int) -> SpamModelORM:
    model = session.scalar(select(SpamModelORM).where(SpamModelORM.name == name))
    if model is not None:
        return model

    model = SpamModelORM(name=name, cost_per_email=cost_per_email)
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def top_up_balance(session: Session, user: UserORM, amount: int) -> TransactionORM:
    if amount <= 0:
        raise ValueError("Сумма пополнения должна быть положительной")

    user.balance.amount += amount
    user.balance.updated_at = datetime.utcnow()
    transaction = TransactionORM(
        user_id=user.id,
        amount=amount,
        transaction_type="top_up",
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def charge_balance(
    session: Session,
    user: UserORM,
    amount: int,
    prediction_request: PredictionRequestORM | None = None,
) -> TransactionORM:
    if amount <= 0:
        raise ValueError("Сумма списания должна быть положительной")
    if user.balance.amount < amount:
        raise ValueError("Недостаточно средств")

    user.balance.amount -= amount
    user.balance.updated_at = datetime.utcnow()
    transaction = TransactionORM(
        user_id=user.id,
        amount=amount,
        transaction_type="charge",
        prediction_request_id=prediction_request.id if prediction_request else None,
    )
    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


def create_prediction_request(
    session: Session,
    user: UserORM,
    model: SpamModelORM,
) -> PredictionRequestORM:
    request = PredictionRequestORM(
        user_id=user.id,
        model_id=model.id,
        status=PredictionStatus.CREATED.value,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def complete_prediction_request(
    session: Session,
    request: PredictionRequestORM,
    charged: int,
    predictions: list[dict],
    errors: list[dict],
) -> PredictionRequestORM:
    request.status = PredictionStatus.DONE.value
    request.charged = charged

    for prediction in predictions:
        session.add(
            EmailPredictionORM(
                request_id=request.id,
                subject=prediction["subject"],
                body=prediction["body"],
                label=prediction.get("label", EmailLabel.HAM.value),
                probability=prediction.get("probability", 0.0),
            )
        )

    for error in errors:
        session.add(
            ValidationErrorORM(
                request_id=request.id,
                row=error["row"],
                field=error["field"],
                message=error["message"],
            )
        )

    session.commit()
    session.refresh(request)
    return request


def get_prediction_history(session: Session, user: UserORM) -> list[PredictionRequestORM]:
    return list(
        session.scalars(
            select(PredictionRequestORM)
            .where(PredictionRequestORM.user_id == user.id)
            .order_by(PredictionRequestORM.created_at.desc())
        )
    )


def get_transaction_history(session: Session, user: UserORM) -> list[TransactionORM]:
    return list(
        session.scalars(
            select(TransactionORM)
            .where(TransactionORM.user_id == user.id)
            .order_by(TransactionORM.created_at.desc())
        )
    )
