from fastapi import APIRouter, Depends

from ..orm import UserORM
from ..schemas import UserResponse
from .common import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(user: UserORM = Depends(get_current_user)) -> UserResponse:
    return UserResponse(email=user.email, role=user.role, balance=user.balance.amount)
