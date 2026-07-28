import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Spam/Ham ML Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database_host": os.getenv("DATABASE_HOST", "database"),
        "database_name": os.getenv("POSTGRES_DB", "ml_service"),
        "rabbitmq_host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
    }
