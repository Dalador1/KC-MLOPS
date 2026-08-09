import time

import requests

from .conftest import BASE_URL, TestUser


def get_balance(api: requests.Session, user: TestUser) -> int:
    response = api.get(f"{BASE_URL}/balance", headers=user.headers, timeout=10)
    assert response.status_code == 200, response.text
    return response.json()["balance"]


def wait_for_prediction(
    api: requests.Session,
    user: TestUser,
    task_id: str,
    timeout: int = 60,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = api.get(
            f"{BASE_URL}/predict/{task_id}",
            headers=user.headers,
            timeout=10,
        )
        assert response.status_code == 200, response.text
        result = response.json()
        if result["status"] in {"done", "failed"}:
            return result
        time.sleep(1)
    raise AssertionError(f"Задача {task_id} не завершилась за {timeout} секунд")
