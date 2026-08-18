from datetime import datetime
import json
import logging
import os
import socket
from time import sleep

import pika
from pydantic import BaseModel, ValidationError

from .api_client import WorkerApiClient, WorkerApiRejected, WorkerApiUnavailable
from .logging_config import setup_logging
from .ml_predictor import SpamPredictor


setup_logging()
logger = logging.getLogger(__name__)
QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "spam_prediction_tasks")


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


def connection_parameters() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        credentials=pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "guest"),
            os.getenv("RABBITMQ_PASSWORD", "guest"),
        ),
        heartbeat=60,
        blocked_connection_timeout=30,
    )


def predict_task(task: PredictionTask, predictor: SpamPredictor) -> tuple[list, list]:
    if task.model != predictor.model_name:
        raise ValueError(f"Модель {task.model} не поддерживается воркером")

    predictions = []
    errors = []
    valid_rows = []
    for row, email in enumerate(task.features.emails):
        if email.body.strip():
            valid_rows.append((row, email))
        else:
            errors.append({"row": row, "field": "body", "message": "Пустое тело письма"})

    if valid_rows:
        texts = [f"{email.subject}\n{email.body}" for _, email in valid_rows]
        model_results = predictor.predict(texts)
        for (_, email), (label, probability) in zip(valid_rows, model_results):
            predictions.append(
                {
                    "subject": email.subject,
                    "body": email.body,
                    "label": label,
                    "probability": probability,
                }
            )
    return predictions, errors


def run_worker() -> None:
    worker_id = os.getenv("WORKER_ID", socket.gethostname())
    api = WorkerApiClient()
    logger.info("%s: loading %s", worker_id, os.getenv("ML_MODEL_NAME"))
    predictor = SpamPredictor()
    logger.info("%s: model loaded", worker_id)

    while True:
        try:
            connection = pika.BlockingConnection(connection_parameters())
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
            if not api.mark_processing(task.task_id, worker_id):
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return
            predictions, errors = predict_task(task, predictor)
            api.complete(task.task_id, worker_id, predictions, errors)
            logger.info(
                "prediction_processed worker_id=%s task_id=%s predictions=%s errors=%s",
                worker_id,
                task.task_id,
                len(predictions),
                len(errors),
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except WorkerApiUnavailable:
            logger.exception("%s cannot save task %s", worker_id, task_id)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except (ValueError, ValidationError, json.JSONDecodeError, WorkerApiRejected) as exc:
            logger.error("%s failed task %s: %s", worker_id, task_id, exc)
            try:
                if task_id != "unknown":
                    api.fail(task_id, worker_id, str(exc))
                channel.basic_ack(delivery_tag=method.delivery_tag)
            except WorkerApiUnavailable:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except WorkerApiRejected:
                channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            logger.exception("%s failed task %s", worker_id, task_id)
            try:
                if task_id != "unknown":
                    api.fail(task_id, worker_id, str(exc))
                channel.basic_ack(delivery_tag=method.delivery_tag)
            except WorkerApiUnavailable:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except WorkerApiRejected:
                channel.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
    logger.info("%s waiting for tasks in %s", worker_id, QUEUE_NAME)
    channel.start_consuming()


if __name__ == "__main__":
    run_worker()
