from .database import SessionLocal
from .init_db import init_db
from .models.enums import UserRole
from .services import (
    charge_balance,
    complete_prediction_request,
    create_prediction_request,
    create_spam_model,
    create_user,
    get_prediction_history,
    get_transaction_history,
    top_up_balance,
)


def run_check() -> None:
    init_db()

    with SessionLocal() as session:
        user = create_user(
            session=session,
            email="check@example.com",
            password_hash="check_password_hash",
            role=UserRole.USER,
        )
        model = create_spam_model(session, name="spam-ham-check", cost_per_email=2)

        top_up_balance(session, user=user, amount=20)
        request = create_prediction_request(session, user=user, model=model)
        charge_balance(session, user=user, amount=model.cost_per_email, prediction_request=request)
        complete_prediction_request(
            session=session,
            request=request,
            charged=model.cost_per_email,
            predictions=[
                {
                    "subject": "Sale",
                    "body": "Buy now",
                    "label": "spam",
                    "probability": 0.92,
                }
            ],
            errors=[],
        )

        predictions = get_prediction_history(session, user)
        transactions = get_transaction_history(session, user)

        print("user:", user.email)
        print("balance:", user.balance.amount)
        print("prediction_requests:", len(predictions))
        print("transactions:", len(transactions))


if __name__ == "__main__":
    run_check()
