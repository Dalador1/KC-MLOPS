import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.email import EmailMessage, EmailValidator
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


class ModelNotFoundError(Exception):
    pass


class InsufficientBalanceError(Exception):
    pass


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate_user(session: Session, email: str, password: str) -> UserORM | None:
    user = get_user(session, email)
    if user is None:
        return None
    if user.password_hash != hash_password(password):
        return None
    return user


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


def get_spam_model(session: Session, name: str) -> SpamModelORM | None:
    return session.scalar(select(SpamModelORM).where(SpamModelORM.name == name))


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


def mock_spam_ham_predict(email: EmailMessage, source: dict) -> dict:
    text = email.text_for_model().lower()
    spam_words = ("free", "buy", "sale", "win", "скидка", "купить", "акция")
    is_spam = any(word in text for word in spam_words)
    return {
        "subject": source["subject"],
        "body": source["body"],
        "label": EmailLabel.SPAM.value if is_spam else EmailLabel.HAM.value,
        "probability": 0.9 if is_spam else 0.8,
    }


def process_prediction_request(
    session: Session,
    user: UserORM,
    model_name: str,
    emails: list[dict],
) -> dict:
    model = get_spam_model(session, model_name)
    if model is None:
        raise ModelNotFoundError("ML-модель не найдена")

    email_messages = [
        EmailMessage(subject=email["subject"], body=email["body"])
        for email in emails
    ]
    valid_emails, validation_errors = EmailValidator().validate(email_messages)

    errors = [
        {
            "row": error._row,
            "field": error._field,
            "message": error._message,
        }
        for error in validation_errors
    ]

    valid_rows = [
        (row, email)
        for row, email in enumerate(email_messages)
        if email.is_valid()
    ]
    charged = model.cost_per_email * len(valid_emails)

    if charged > 0 and user.balance.amount < charged:
        raise InsufficientBalanceError("Недостаточно средств")

    request = create_prediction_request(session, user, model)
    predictions = [
        mock_spam_ham_predict(email, emails[row])
        for row, email in valid_rows
    ]

    if charged > 0:
        charge_balance(session, user, charged, request)

    complete_prediction_request(
        session=session,
        request=request,
        charged=charged,
        predictions=predictions,
        errors=errors,
    )

    return {
        "request_id": request.id,
        "status": request.status,
        "charged": charged,
        "balance": user.balance.amount,
        "predictions": predictions,
        "errors": errors,
    }
