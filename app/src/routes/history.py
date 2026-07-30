from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import HistoryAuthRequest, PredictionHistoryItem, TransactionHistoryItem
from ..services import get_prediction_history, get_transaction_history
from .common import require_user

router = APIRouter(prefix="/history", tags=["history"])


@router.post("/predictions", response_model=list[PredictionHistoryItem])
def prediction_history(
    data: HistoryAuthRequest,
    session: Session = Depends(get_session),
) -> list[PredictionHistoryItem]:
    user = require_user(session, data.email, data.password)
    requests = get_prediction_history(session, user)
    return [
        PredictionHistoryItem(
            id=request.id,
            model_name=request.model.name,
            status=request.status,
            charged=request.charged,
            created_at=request.created_at,
            predictions_count=len(request.predictions),
            errors_count=len(request.validation_errors),
        )
        for request in requests
    ]


@router.post("/transactions", response_model=list[TransactionHistoryItem])
def transaction_history(
    data: HistoryAuthRequest,
    session: Session = Depends(get_session),
) -> list[TransactionHistoryItem]:
    user = require_user(session, data.email, data.password)
    transactions = get_transaction_history(session, user)
    return [
        TransactionHistoryItem(
            id=transaction.id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            prediction_request_id=transaction.prediction_request_id,
            created_at=transaction.created_at,
        )
        for transaction in transactions
    ]
