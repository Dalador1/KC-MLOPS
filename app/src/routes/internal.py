import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import (
    WorkerFailureRequest,
    WorkerProcessingRequest,
    WorkerProcessingResponse,
    WorkerResultRequest,
)
from ..services import (
    fail_prediction_request,
    get_prediction_request_by_task_id,
    save_worker_result,
    start_worker_processing,
)


router = APIRouter(prefix="/internal/predictions", tags=["internal"])


def require_worker_token(x_worker_token: str | None = Header(default=None)) -> None:
    expected_token = os.getenv("WORKER_API_TOKEN", "local-worker-secret")
    if x_worker_token is None or not hmac.compare_digest(x_worker_token, expected_token):
        raise HTTPException(status_code=401, detail="Некорректный токен воркера")


@router.post("/{task_id}/processing", response_model=WorkerProcessingResponse)
def processing(
    task_id: str,
    data: WorkerProcessingRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> WorkerProcessingResponse:
    try:
        should_process = start_worker_processing(session, task_id, data.worker_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkerProcessingResponse(should_process=should_process)


@router.post("/{task_id}/complete", status_code=204)
def complete(
    task_id: str,
    data: WorkerResultRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> None:
    try:
        save_worker_result(
            session=session,
            task_id=task_id,
            worker_id=data.worker_id,
            predictions=[item.model_dump() for item in data.predictions],
            errors=[item.model_dump() for item in data.errors],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/fail", status_code=204)
def fail(
    task_id: str,
    data: WorkerFailureRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> None:
    request = get_prediction_request_by_task_id(session, task_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    request.worker_id = data.worker_id
    fail_prediction_request(session, request, data.message)
