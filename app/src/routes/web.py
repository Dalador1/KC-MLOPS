import os
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..database import get_session
from ..models.enums import UserRole
from ..orm import UserORM
from ..schemas import LoginRequest, RegisterRequest
from ..security import TOKEN_TTL_MINUTES, create_access_token, get_email_from_token
from ..services import (
    InsufficientBalanceError,
    ModelNotFoundError,
    QueueUnavailableError,
    authenticate_user,
    create_user,
    get_prediction_history,
    get_prediction_request_by_task_id,
    get_transaction_history,
    get_user,
    hash_password,
    submit_prediction_task,
    top_up_balance,
)


router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")
COOKIE_NAME = "access_token"
MODEL_NAME = "RUSpam/spam_deberta_v4"


def web_user(request: Request, session: Session) -> UserORM | None:
    token = request.cookies.get(COOKIE_NAME)
    email = get_email_from_token(token) if token else None
    return get_user(session, email) if email else None


def set_auth_cookie(response: RedirectResponse, email: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(email),
        max_age=TOKEN_TTL_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    )


def login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def dashboard_redirect(**params: str) -> RedirectResponse:
    return RedirectResponse(f"/dashboard?{urlencode(params)}", status_code=303)


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"page": "home", "user": web_user(request, session)},
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    if web_user(request, session):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"page": "login", "user": None},
    )


@router.post("/web/login")
def web_login(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    session: Session = Depends(get_session),
):
    try:
        data = LoginRequest(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"page": "login", "user": None, "error": "Проверьте email и пароль"},
            status_code=422,
        )
    user = authenticate_user(session, data.email, data.password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"page": "login", "user": None, "error": "Неверный email или пароль"},
            status_code=401,
        )
    response = RedirectResponse("/dashboard", status_code=303)
    set_auth_cookie(response, user.email)
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, session: Session = Depends(get_session)):
    if web_user(request, session):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"page": "register", "user": None},
    )


@router.post("/web/register")
def web_register(
    request: Request,
    email: str = Form(),
    password: str = Form(),
    session: Session = Depends(get_session),
):
    try:
        data = RegisterRequest(email=email, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"page": "register", "user": None, "error": "Проверьте email и пароль"},
            status_code=422,
        )
    if get_user(session, data.email):
        return templates.TemplateResponse(
            request,
            "index.html",
            {"page": "register", "user": None, "error": "Пользователь уже существует"},
            status_code=409,
        )
    user = create_user(
        session,
        data.email,
        hash_password(data.password),
        role=UserRole.USER,
        initial_balance=0,
    )
    response = RedirectResponse("/dashboard", status_code=303)
    set_auth_cookie(response, user.email)
    return response


@router.post("/web/logout")
def web_logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if user is None:
        return login_redirect()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "page": "dashboard",
            "user": user,
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/web/balance/top-up")
def web_top_up(
    request: Request,
    amount: int = Form(),
    session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if user is None:
        return login_redirect()
    try:
        top_up_balance(session, user, amount)
    except ValueError as exc:
        return dashboard_redirect(error=str(exc))
    return dashboard_redirect(message=f"Баланс пополнен на {amount} кредитов")


@router.post("/web/predict")
def web_predict(
    request: Request,
    subject: list[str] = Form(),
    body: list[str] = Form(),
    session: Session = Depends(get_session),
):
    user = web_user(request, session)
    if user is None:
        return login_redirect()
    emails = [
        {"subject": item_subject, "body": item_body}
        for item_subject, item_body in zip(subject, body)
        if item_subject.strip() or item_body.strip()
    ]
    if not emails:
        return dashboard_redirect(error="Добавьте хотя бы одно письмо")
    try:
        task = submit_prediction_task(session, user, MODEL_NAME, emails)
    except (ModelNotFoundError, InsufficientBalanceError, QueueUnavailableError) as exc:
        return dashboard_redirect(error=str(exc))
    return RedirectResponse(f"/tasks/{task.task_id}", status_code=303)


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def task_page(task_id: str, request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if user is None:
        return login_redirect()
    task = get_prediction_request_by_task_id(session, task_id)
    if task is None or task.user_id != user.id:
        return RedirectResponse(f"/history?{urlencode({'error': 'Задача не найдена'})}", status_code=303)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"page": "task", "user": user, "task": task},
    )


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, session: Session = Depends(get_session)):
    user = web_user(request, session)
    if user is None:
        return login_redirect()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "page": "history",
            "user": user,
            "predictions": get_prediction_history(session, user),
            "transactions": get_transaction_history(session, user),
            "error": request.query_params.get("error"),
        },
    )
