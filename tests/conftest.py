import os
from dataclasses import dataclass
from uuid import uuid4

import pytest
import requests


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost").rstrip("/")


@dataclass
class TestUser:
    email: str
    password: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture(scope="session")
def api() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def user_factory(api: requests.Session):
    def create(initial_top_up: int = 0) -> TestUser:
        email = f"pytest-{uuid4().hex}@example.com"
        password = "test-password"
        registration = api.post(
            f"{BASE_URL}/auth/register",
            json={"email": email, "password": password},
            timeout=10,
        )
        assert registration.status_code == 201, registration.text
        registration_data = registration.json()
        assert registration_data == {"email": email, "role": "user", "balance": 0}

        login = api.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        assert login.status_code == 200, login.text
        user = TestUser(email=email, password=password, token=login.json()["access_token"])

        if initial_top_up:
            top_up = api.post(
                f"{BASE_URL}/balance/top-up",
                headers=user.headers,
                json={"amount": initial_top_up},
                timeout=10,
            )
            assert top_up.status_code == 200, top_up.text
        return user

    return create
