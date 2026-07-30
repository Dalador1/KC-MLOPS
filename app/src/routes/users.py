from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import LoginRequest, UserResponse
from .common import require_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me", response_model=UserResponse)
def get_current_user(data: LoginRequest, session: Session = Depends(get_session)) -> UserResponse:
    user = require_user(session, data.email, data.password)
    return UserResponse(email=user.email, role=user.role, balance=user.balance.amount)
