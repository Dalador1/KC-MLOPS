from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pika.exceptions import AMQPError
from sqlalchemy.orm import Session

from ..database import get_session
from ..orm import UserORM
from ..models.enums import PredictionStatus
from ..rabbitmq import publish_prediction_task
from ..schemas import PredictAcceptedResponse, PredictRequest, PredictResponse
from ..services import (
    create_prediction_request,
    fail_prediction_request,
    get_prediction_request_by_task_id,
    get_spam_model,
)
from .common import get_current_user

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post(
    "",
    response_model=PredictAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def predict(
    data: PredictRequest,
    session: Session = Depends(get_session),
    user: UserORM = Depends(get_current_user),
) -> PredictAcceptedResponse:
    model = get_spam_model(session, data.model_name)
    if model is None:
        raise HTTPException(status_code=404, detail="ML-модель не найдена")

    valid_emails_count = sum(bool(email.body.strip()) for email in data.emails)
    expected_charge = model.cost_per_email * valid_emails_count
    if user.balance.amount < expected_charge:
        raise HTTPException(status_code=402, detail="Недостаточно средств")

    task_id = str(uuid4())
    request = create_prediction_request(
        session=session,
        user=user,
        model=model,
        task_id=task_id,
        status=PredictionStatus.QUEUED,
    )
    emails = [email.model_dump() for email in data.emails]

    try:
        publish_prediction_task(task_id, data.model_name, user.id, emails)
    except AMQPError as exc:
        fail_prediction_request(session, request, "RabbitMQ недоступен")
        raise HTTPException(status_code=503, detail="Очередь временно недоступна") from exc

    return PredictAcceptedResponse(task_id=task_id, status=request.status)


@router.get("/{task_id}", response_model=PredictResponse)
def prediction_result(
    task_id: str,
    session: Session = Depends(get_session),
    user: UserORM = Depends(get_current_user),
) -> PredictResponse:
    request = get_prediction_request_by_task_id(session, task_id)
    if request is None or request.user_id != user.id:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return PredictResponse(
        task_id=task_id,
        request_id=request.id,
        status=request.status,
        charged=request.charged,
        worker_id=request.worker_id,
        error_message=request.error_message,
        predictions=[
            {
                "subject": prediction.subject,
                "body": prediction.body,
                "label": prediction.label,
                "probability": prediction.probability,
            }
            for prediction in request.predictions
        ],
        errors=[
            {
                "row": error.row,
                "field": error.field,
                "message": error.message,
            }
            for error in request.validation_errors
        ],
    )
