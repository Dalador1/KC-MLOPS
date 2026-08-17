import json
import logging
import os
from datetime import datetime, timezone

import pika


QUEUE_NAME = os.getenv("RABBITMQ_QUEUE", "spam_prediction_tasks")
logger = logging.getLogger(__name__)


def _connection_parameters() -> pika.ConnectionParameters:
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


def publish_prediction_task(
    task_id: str,
    model_name: str,
    user_id: int,
    emails: list[dict],
) -> None:
    message = {
        "task_id": task_id,
        "features": {"emails": emails},
        "model": model_name,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    with pika.BlockingConnection(_connection_parameters()) as connection:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=pika.DeliveryMode.Persistent,
            ),
        )
    logger.info(
        "rabbitmq_message_published task_id=%s queue=%s model=%s",
        task_id,
        QUEUE_NAME,
        model_name,
    )
