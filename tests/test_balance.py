from .conftest import BASE_URL
from .helpers import get_balance


def test_balance_top_up_and_transaction_history(api, user_factory):
    user = user_factory()
    assert get_balance(api, user) == 0

    top_up = api.post(
        f"{BASE_URL}/balance/top-up",
        headers=user.headers,
        json={"amount": 17},
        timeout=10,
    )

    assert top_up.status_code == 200
    assert top_up.json()["balance"] == 17
    assert get_balance(api, user) == 17

    history = api.get(
        f"{BASE_URL}/history/transactions",
        headers=user.headers,
        timeout=10,
    )
    assert history.status_code == 200
    assert any(
        item["transaction_type"] == "top_up" and item["amount"] == 17
        for item in history.json()
    )


def test_non_positive_top_up_is_rejected(api, user_factory):
    user = user_factory()

    response = api.post(
        f"{BASE_URL}/balance/top-up",
        headers=user.headers,
        json={"amount": 0},
        timeout=10,
    )

    assert response.status_code == 422
    assert get_balance(api, user) == 0
