import hashlib
from datetime import datetime
from uuid import uuid4

from pika.exceptions import AMQPError
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
from .rabbitmq import publish_prediction_task


class ModelNotFoundError(Exception):
    pass


class InsufficientBalanceError(Exception):
    pass


class QueueUnavailableError(Exception):
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
    task_id: str | None = None,
    status: PredictionStatus = PredictionStatus.CREATED,
) -> PredictionRequestORM:
    request = PredictionRequestORM(
        task_id=task_id,
        user_id=user.id,
        model_id=model.id,
        status=status.value,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def submit_prediction_task(
    session: Session,
    user: UserORM,
    model_name: str,
    emails: list[dict],
) -> PredictionRequestORM:
    model = get_spam_model(session, model_name)
    if model is None:
        raise ModelNotFoundError("ML-модель не найдена")
    if user.balance.amount <= 0:
        raise InsufficientBalanceError("Пополните баланс перед проверкой")

    valid_emails_count = sum(bool(email["body"].strip()) for email in emails)
    expected_charge = model.cost_per_email * valid_emails_count
    if user.balance.amount < expected_charge:
        raise InsufficientBalanceError("Недостаточно средств")

    task_id = str(uuid4())
    request = create_prediction_request(
        session=session,
        user=user,
        model=model,
        task_id=task_id,
        status=PredictionStatus.QUEUED,
    )
    try:
        publish_prediction_task(task_id, model_name, user.id, emails)
    except AMQPError as exc:
        fail_prediction_request(session, request, "RabbitMQ недоступен")
        raise QueueUnavailableError("Очередь временно недоступна") from exc
    return request


def get_prediction_request_by_task_id(
    session: Session,
    task_id: str,
) -> PredictionRequestORM | None:
    return session.scalar(
        select(PredictionRequestORM).where(PredictionRequestORM.task_id == task_id)
    )


def fail_prediction_request(
    session: Session,
    request: PredictionRequestORM,
    message: str,
) -> None:
    request.status = PredictionStatus.FAILED.value
    request.error_message = message[:500]
    session.commit()


def start_worker_processing(
    session: Session,
    task_id: str,
    worker_id: str,
) -> bool:
    request = session.scalar(
        select(PredictionRequestORM)
        .where(PredictionRequestORM.task_id == task_id)
        .with_for_update()
    )
    if request is None:
        raise LookupError("Задача не найдена")
    if request.status == PredictionStatus.DONE.value:
        return False

    request.status = PredictionStatus.PROCESSING.value
    request.worker_id = worker_id
    request.error_message = None
    session.commit()
    return True


def save_worker_result(
    session: Session,
    task_id: str,
    worker_id: str,
    predictions: list[dict],
    errors: list[dict],
) -> PredictionRequestORM:
    request = session.scalar(
        select(PredictionRequestORM)
        .where(PredictionRequestORM.task_id == task_id)
        .with_for_update()
    )
    if request is None:
        raise LookupError("Задача не найдена")
    if request.status == PredictionStatus.DONE.value:
        return request

    balance = session.scalar(
        select(CreditBalanceORM)
        .where(CreditBalanceORM.user_id == request.user_id)
        .with_for_update()
    )
    charged = request.model.cost_per_email * len(predictions)
    if balance is None or balance.amount < charged:
        raise ValueError("Недостаточно средств")

    for prediction in predictions:
        session.add(
            EmailPredictionORM(
                request_id=request.id,
                subject=prediction["subject"],
                body=prediction["body"],
                label=prediction["label"],
                probability=prediction["probability"],
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

    if charged:
        balance.amount -= charged
        balance.updated_at = datetime.utcnow()
        session.add(
            TransactionORM(
                user_id=request.user_id,
                amount=charged,
                transaction_type="charge",
                prediction_request_id=request.id,
            )
        )

    request.status = PredictionStatus.DONE.value
    request.charged = charged
    request.worker_id = worker_id
    request.error_message = None
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
