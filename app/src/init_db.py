from time import sleep

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from .database import SessionLocal, engine
from .models.enums import UserRole
from .orm import Base
from .services import create_spam_model, create_user, hash_password, top_up_balance


def migrate_prediction_requests() -> None:
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("prediction_requests")
    }
    migrations = {
        "task_id": "ALTER TABLE prediction_requests ADD COLUMN IF NOT EXISTS task_id VARCHAR(36)",
        "worker_id": "ALTER TABLE prediction_requests ADD COLUMN IF NOT EXISTS worker_id VARCHAR(120)",
        "error_message": (
            "ALTER TABLE prediction_requests "
            "ADD COLUMN IF NOT EXISTS error_message VARCHAR(500)"
        ),
    }
    with engine.begin() as connection:
        for column, statement in migrations.items():
            if column not in columns:
                connection.execute(text(statement))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_prediction_requests_task_id "
                "ON prediction_requests (task_id)"
            )
        )


def init_db() -> None:
    for attempt in range(30):
        try:
            Base.metadata.create_all(bind=engine)
            migrate_prediction_requests()
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
        create_spam_model(session, name="RUSpam/spam_deberta_v4", cost_per_email=1)

        if user.balance.amount == 0:
            top_up_balance(session, user=user, amount=100)

        user.password_hash = hash_password("demo")
        admin.password_hash = hash_password("admin")
        session.commit()


if __name__ == "__main__":
    init_db()
