from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..orm import UserORM
from ..services import authenticate_user


def require_user(session: Session, email: str, password: str) -> UserORM:
    user = authenticate_user(session, email, password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    return user
