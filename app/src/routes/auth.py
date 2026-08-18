from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..models.enums import UserRole
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from ..security import TOKEN_TTL_MINUTES, create_access_token
from ..services import authenticate_user, create_user, get_user, hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: Session = Depends(get_session)) -> UserResponse:
    if get_user(session, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь уже существует",
        )

    user = create_user(
        session=session,
        email=data.email,
        password_hash=hash_password(data.password),
        role=UserRole.USER,
        initial_balance=0,
    )
    return UserResponse(email=user.email, role=user.role, balance=user.balance.amount)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    user = authenticate_user(session, data.email, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    return TokenResponse(
        access_token=create_access_token(user.email),
        expires_in_minutes=TOKEN_TTL_MINUTES,
    )
