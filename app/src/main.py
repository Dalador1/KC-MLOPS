import os

from fastapi import FastAPI


app = FastAPI(title="Spam/Ham ML Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database_host": os.getenv("DATABASE_HOST", "database"),
        "rabbitmq_host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
    }
