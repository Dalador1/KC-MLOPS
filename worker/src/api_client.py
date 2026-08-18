import json
import os
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class WorkerApiUnavailable(Exception):
    pass


class WorkerApiRejected(Exception):
    pass


class WorkerApiClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("APP_API_URL", "http://app:8000").rstrip("/")
        self.token = os.getenv("WORKER_API_TOKEN", "local-worker-secret")

    def _post(self, path: str, payload: dict) -> dict | None:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Worker-Token": self.token,
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=30) as response:
                    body = response.read()
                    return json.loads(body) if body else None
            except HTTPError as exc:
                raise WorkerApiRejected(f"App вернул HTTP {exc.code}") from exc
            except URLError as exc:
                if attempt == 2:
                    raise WorkerApiUnavailable("App недоступен") from exc
                sleep(2)
        return None

    def mark_processing(self, task_id: str, worker_id: str) -> bool:
        response = self._post(
            f"/internal/predictions/{task_id}/processing",
            {"worker_id": worker_id},
        )
        return bool(response and response["should_process"])

    def complete(
        self,
        task_id: str,
        worker_id: str,
        predictions: list[dict],
        errors: list[dict],
    ) -> None:
        self._post(
            f"/internal/predictions/{task_id}/complete",
            {
                "worker_id": worker_id,
                "predictions": predictions,
                "errors": errors,
            },
        )

    def fail(self, task_id: str, worker_id: str, message: str) -> None:
        self._post(
            f"/internal/predictions/{task_id}/fail",
            {"worker_id": worker_id, "message": message[:500]},
        )
