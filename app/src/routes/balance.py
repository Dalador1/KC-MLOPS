from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..orm import UserORM
from ..schemas import BalanceResponse, TopUpRequest
from ..services import top_up_balance
from .common import get_current_user

router = APIRouter(prefix="/balance", tags=["balance"])


@router.get("", response_model=BalanceResponse)
def get_balance(
    user: UserORM = Depends(get_current_user),
) -> BalanceResponse:
    return BalanceResponse(balance=user.balance.amount)


@router.post("/top-up", response_model=BalanceResponse)
def top_up(
    data: TopUpRequest,
    session: Session = Depends(get_session),
    user: UserORM = Depends(get_current_user),
) -> BalanceResponse:
    top_up_balance(session, user, data.amount)
    return BalanceResponse(balance=user.balance.amount)
