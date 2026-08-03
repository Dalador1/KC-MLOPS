from datetime import datetime
import json
import logging
import os
import socket
from time import sleep

import pika
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from .database import SessionLocal
from .init_db import init_db
from .ml_predictor import SpamPredictor
from .models.email import EmailMessage, EmailValidator
from .models.enums import PredictionStatus
from .orm import (
    CreditBalanceORM,
    EmailPredictionORM,
    PredictionRequestORM,
    TransactionORM,
    ValidationErrorORM,
)
from .rabbitmq import QUEUE_NAME, _connection_parameters


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class EmailPayload(BaseModel):
    subject: str = ""
    body: str = ""


class FeaturesPayload(BaseModel):
    emails: list[EmailPayload]


class PredictionTask(BaseModel):
    task_id: str
    features: FeaturesPayload
    model: str
    user_id: int
    timestamp: datetime


def save_failed_task(task_id: str, worker_id: str, message: str) -> None:
    with SessionLocal() as session:
        request = session.scalar(
            select(PredictionRequestORM).where(PredictionRequestORM.task_id == task_id)
        )
        if request is not None:
            request.status = PredictionStatus.FAILED.value
            request.worker_id = worker_id
            request.error_message = message[:500]
            session.commit()


def process_task(task: PredictionTask, predictor: SpamPredictor, worker_id: str) -> None:
    if task.model != predictor.model_name:
        raise ValueError(f"Модель {task.model} не поддерживается воркером")

    with SessionLocal() as session:
        request = session.scalar(
            select(PredictionRequestORM).where(PredictionRequestORM.task_id == task.task_id)
        )
        if request is None:
            raise ValueError("Задача отсутствует в базе данных")
        if request.status == PredictionStatus.DONE.value:
            return

        request.status = PredictionStatus.PROCESSING.value
        request.worker_id = worker_id
        session.commit()

        sources = [email.model_dump() for email in task.features.emails]
        messages = [EmailMessage(item["subject"], item["body"]) for item in sources]
        valid_messages, validation_errors = EmailValidator().validate(messages)
        valid_rows = [(row, email) for row, email in enumerate(messages) if email.is_valid()]

        predictions = (
            predictor.predict([email.text_for_model() for email in valid_messages])
            if valid_messages
            else []
        )
        charged = request.model.cost_per_email * len(valid_messages)

        balance = session.scalar(
            select(CreditBalanceORM)
            .where(CreditBalanceORM.user_id == task.user_id)
            .with_for_update()
        )
        if balance is None or balance.amount < charged:
            raise ValueError("Недостаточно средств")

        for (row, _), (label, probability) in zip(valid_rows, predictions):
            session.add(
                EmailPredictionORM(
                    request_id=request.id,
                    subject=sources[row]["subject"],
                    body=sources[row]["body"],
                    label=label,
                    probability=probability,
                )
            )
        for error in validation_errors:
            session.add(
                ValidationErrorORM(
                    request_id=request.id,
                    row=error._row,
                    field=error._field,
                    message=error._message,
                )
            )

        if charged:
            balance.amount -= charged
            balance.updated_at = datetime.utcnow()
            session.add(
                TransactionORM(
                    user_id=task.user_id,
                    amount=charged,
                    transaction_type="charge",
                    prediction_request_id=request.id,
                )
            )
        request.status = PredictionStatus.DONE.value
        request.charged = charged
        request.error_message = None
        session.commit()


def run_worker() -> None:
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    init_db()
    logger.info("%s: loading %s", worker_id, os.getenv("ML_MODEL_NAME"))
    predictor = SpamPredictor()
    logger.info("%s: model loaded", worker_id)

    while True:
        try:
            connection = pika.BlockingConnection(_connection_parameters())
            break
        except pika.exceptions.AMQPConnectionError:
            logger.warning("%s: RabbitMQ is not ready, retrying", worker_id)
            sleep(3)

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.basic_qos(prefetch_count=1)

    def callback(channel, method, properties, body: bytes) -> None:
        task_id = "unknown"
        try:
            payload = json.loads(body)
            task_id = str(payload.get("task_id", "unknown"))
            task = PredictionTask.model_validate(payload)
            process_task(task, predictor, worker_id)
            logger.info("%s processed task %s", worker_id, task.task_id)
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            logger.error("%s failed task %s: %s", worker_id, task_id, exc)
            if task_id != "unknown":
                save_failed_task(task_id, worker_id, str(exc))
        except Exception as exc:
            logger.exception("%s failed task %s", worker_id, task_id)
            if task_id != "unknown":
                save_failed_task(task_id, worker_id, str(exc))
        finally:
            channel.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    logger.info("%s waiting for tasks in %s", worker_id, QUEUE_NAME)
    channel.start_consuming()


if __name__ == "__main__":
    run_worker()
