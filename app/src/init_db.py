from time import sleep

from sqlalchemy.exc import OperationalError

from .database import SessionLocal, engine
from .models.enums import UserRole
from .orm import Base
from .services import create_spam_model, create_user, hash_password, top_up_balance


def init_db() -> None:
    for attempt in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError:
            if attempt == 29:
                raise
            sleep(2)

    with SessionLocal() as session:
        user = create_user(
            session=session,
            email="demo@example.com",
            password_hash=hash_password("demo"),
            role=UserRole.USER,
            initial_balance=0,
        )
        admin = create_user(
            session=session,
            email="admin@example.com",
            password_hash=hash_password("admin"),
            role=UserRole.ADMIN,
            initial_balance=0,
        )
        create_spam_model(session, name="spam-ham-default", cost_per_email=1)

        if user.balance.amount == 0:
            top_up_balance(session, user=user, amount=100)

        user.password_hash = hash_password("demo")
        admin.password_hash = hash_password("admin")
        session.commit()


if __name__ == "__main__":
    init_db()
