from .conftest import BASE_URL


def test_service_health(api):
    response = api.get(f"{BASE_URL}/health", timeout=10)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time"]) >= 0


def test_web_interface_is_available_without_javascript(api):
    response = api.get(f"{BASE_URL}/", timeout=10)

    assert response.status_code == 200
    assert "MailGuard" in response.text
    assert "<script" not in response.text
