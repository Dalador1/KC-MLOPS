import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .init_db import init_db
from .logging_config import setup_logging
from .routes import auth, balance, history, internal, predict, users, web


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_starting")
    init_db()
    logger.info("application_started")
    yield
    logger.info("application_stopped")


app = FastAPI(title="Spam/Ham ML Service", lifespan=lifespan)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost,http://localhost:8000,http://127.0.0.1",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = perf_counter() - started_at
        logger.exception(
            "http_request_failed method=%s path=%s duration=%.4fs request_id=%s",
            request.method,
            request.url.path,
            elapsed,
            request_id,
        )
        raise
    elapsed = perf_counter() - started_at
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    logger.info(
        "http_request method=%s path=%s status=%s duration=%.4fs request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
        request_id,
    )
    return response


app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(balance.router)
app.include_router(predict.router)
app.include_router(history.router)
app.include_router(internal.router, include_in_schema=False)
app.include_router(web.router, include_in_schema=False)


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
