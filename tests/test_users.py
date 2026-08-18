from .conftest import BASE_URL


def test_registration_authorization_and_repeated_login(api, user_factory):
    user = user_factory()

    first_login = api.post(
        f"{BASE_URL}/auth/login",
        json={"email": user.email, "password": user.password},
        timeout=10,
    )
    repeated_login = api.post(
        f"{BASE_URL}/auth/login",
        json={"email": user.email, "password": user.password},
        timeout=10,
    )

    assert first_login.status_code == 200
    assert repeated_login.status_code == 200
    assert first_login.json()["token_type"] == "bearer"
    assert repeated_login.json()["access_token"]


def test_wrong_password_is_rejected(api, user_factory):
    user = user_factory()

    response = api.post(
        f"{BASE_URL}/auth/login",
        json={"email": user.email, "password": "wrong-password"},
        timeout=10,
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Неверный email или пароль"


def test_protected_endpoint_requires_token(api):
    response = api.get(f"{BASE_URL}/balance", timeout=10)

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Не передан Bearer-токен"


def test_invalid_registration_data_is_rejected(api):
    response = api.post(
        f"{BASE_URL}/auth/register",
        json={"email": "not-an-email", "password": "123"},
        timeout=10,
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Ошибка валидации"
