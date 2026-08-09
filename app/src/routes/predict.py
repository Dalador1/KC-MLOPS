from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..orm import UserORM
from ..schemas import PredictAcceptedResponse, PredictRequest, PredictResponse
from ..services import (
    InsufficientBalanceError,
    ModelNotFoundError,
    QueueUnavailableError,
    get_prediction_request_by_task_id,
    submit_prediction_task,
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
    emails = [email.model_dump() for email in data.emails]
    try:
        request = submit_prediction_task(session, user, data.model_name, emails)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InsufficientBalanceError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    except QueueUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return PredictAcceptedResponse(task_id=request.task_id, status=request.status)


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
