from uuid import UUID

from .conftest import BASE_URL
from .helpers import get_balance, wait_for_prediction


MODEL_NAME = "RUSpam/spam_deberta_v4"


def test_prediction_is_rejected_when_balance_is_insufficient(api, user_factory):
    user = user_factory()

    response = api.post(
        f"{BASE_URL}/predict",
        headers=user.headers,
        json={
            "model_name": MODEL_NAME,
            "emails": [{"subject": "Работа", "body": "Встреча завтра утром"}],
        },
        timeout=10,
    )

    assert response.status_code == 402
    assert get_balance(api, user) == 0


def test_ml_request_error_does_not_charge_balance(api, user_factory):
    user = user_factory(initial_top_up=5)
    balance_before = get_balance(api, user)

    response = api.post(
        f"{BASE_URL}/predict",
        headers=user.headers,
        json={
            "model_name": "unknown-model",
            "emails": [{"subject": "Письмо", "body": "Текст письма"}],
        },
        timeout=10,
    )

    assert response.status_code == 404
    assert get_balance(api, user) == balance_before

    transactions = api.get(
        f"{BASE_URL}/history/transactions",
        headers=user.headers,
        timeout=10,
    ).json()
    assert not any(item["transaction_type"] == "charge" for item in transactions)


def test_invalid_request_does_not_charge_balance(api, user_factory):
    user = user_factory(initial_top_up=3)

    response = api.post(
        f"{BASE_URL}/predict",
        headers=user.headers,
        json={"model_name": MODEL_NAME, "emails": []},
        timeout=10,
    )

    assert response.status_code == 422
    assert get_balance(api, user) == 3


def test_partial_batch_prediction_charging_and_history(api, user_factory):
    user = user_factory(initial_top_up=5)
    request = api.post(
        f"{BASE_URL}/predict",
        headers=user.headers,
        json={
            "model_name": MODEL_NAME,
            "emails": [
                {
                    "subject": "Вы выиграли денежный приз",
                    "body": "Срочно перейдите по ссылке и подтвердите банковскую карту",
                },
                {"subject": "Пустое письмо", "body": ""},
            ],
        },
        timeout=10,
    )

    assert request.status_code == 202, request.text
    task_id = request.json()["task_id"]
    assert str(UUID(task_id)) == task_id

    result = wait_for_prediction(api, user, task_id)
    assert result["status"] == "done", result
    assert result["charged"] == 1
    assert len(result["predictions"]) == 1
    assert result["predictions"][0]["label"] in {"spam", "ham"}
    assert 0 <= result["predictions"][0]["probability"] <= 1
    assert result["errors"] == [
        {"row": 1, "field": "body", "message": "Пустое тело письма"}
    ]
    assert get_balance(api, user) == 4

    prediction_history = api.get(
        f"{BASE_URL}/history/predictions",
        headers=user.headers,
        timeout=10,
    )
    assert prediction_history.status_code == 200
    history_item = next(item for item in prediction_history.json() if item["task_id"] == task_id)
    assert history_item["status"] == "done"
    assert history_item["charged"] == 1
    assert history_item["model_name"] == MODEL_NAME
    assert history_item["worker_id"] in {"worker-1", "worker-2"}
    assert history_item["created_at"]
    assert history_item["predictions_count"] == 1
    assert history_item["errors_count"] == 1

    transaction_history = api.get(
        f"{BASE_URL}/history/transactions",
        headers=user.headers,
        timeout=10,
    )
    assert transaction_history.status_code == 200
    assert any(
        item["transaction_type"] == "charge"
        and item["amount"] == 1
        and item["prediction_request_id"] == history_item["id"]
        and item["created_at"]
        for item in transaction_history.json()
    )

    repeated_result = wait_for_prediction(api, user, task_id)
    assert repeated_result == result
    assert get_balance(api, user) == 4
