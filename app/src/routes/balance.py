from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import BalanceAuthRequest, BalanceResponse, TopUpRequest
from ..services import top_up_balance
from .common import require_user

router = APIRouter(prefix="/balance", tags=["balance"])


@router.post("", response_model=BalanceResponse)
def get_balance(
    data: BalanceAuthRequest,
    session: Session = Depends(get_session),
) -> BalanceResponse:
    user = require_user(session, data.email, data.password)
    return BalanceResponse(balance=user.balance.amount)


@router.post("/top-up", response_model=BalanceResponse)
def top_up(data: TopUpRequest, session: Session = Depends(get_session)) -> BalanceResponse:
    user = require_user(session, data.email, data.password)
    top_up_balance(session, user, data.amount)
    return BalanceResponse(balance=user.balance.amount)
