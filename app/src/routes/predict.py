from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..orm import UserORM
from ..schemas import PredictRequest, PredictResponse
from ..services import (
    InsufficientBalanceError,
    ModelNotFoundError,
    process_prediction_request,
)
from .common import get_current_user

router = APIRouter(prefix="/predict", tags=["predict"])


@router.post("", response_model=PredictResponse)
def predict(
    data: PredictRequest,
    session: Session = Depends(get_session),
    user: UserORM = Depends(get_current_user),
) -> PredictResponse:
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
