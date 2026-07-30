from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import PredictRequest, PredictResponse
from ..services import (
    InsufficientBalanceError,
    ModelNotFoundError,
    process_prediction_request,
)
from .common import require_user

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
def predict(data: PredictRequest, session: Session = Depends(get_session)) -> PredictResponse:
    user = require_user(session, data.email, data.password)

    try:
        result = process_prediction_request(
            session=session,
            user=user,
            model_name=data.model_name,
            emails=[email.model_dump() for email in data.emails],
        )
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InsufficientBalanceError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc

    return PredictResponse(**result)
