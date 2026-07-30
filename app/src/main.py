import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .init_db import init_db
from .routes import auth, balance, history, predict, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Spam/Ham ML Service", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(balance.router)
app.include_router(predict.router)
app.include_router(history.router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {"error": {"code": 422, "message": "Ошибка валидации", "details": exc.errors()}}
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "database_host": os.getenv("DATABASE_HOST", "database"),
        "database_name": os.getenv("POSTGRES_DB", "ml_service"),
        "rabbitmq_host": os.getenv("RABBITMQ_HOST", "rabbitmq"),
    }
