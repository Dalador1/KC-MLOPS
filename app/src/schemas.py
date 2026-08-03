from datetime import datetime

from pydantic import BaseModel, Field


class LoginData(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=4)


class RegisterRequest(LoginData):
    pass


class LoginRequest(LoginData):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UserResponse(BaseModel):
    email: str
    role: str
    balance: int


class TopUpRequest(BaseModel):
    amount: int = Field(gt=0)


class BalanceResponse(BaseModel):
    balance: int


class EmailInput(BaseModel):
    subject: str = ""
    body: str = ""


class PredictRequest(BaseModel):
    model_name: str = "spam-ham-default"
    emails: list[EmailInput] = Field(min_length=1)


class ValidationErrorResponse(BaseModel):
    row: int
    field: str
    message: str


class EmailPredictionResponse(BaseModel):
    subject: str
    body: str
    label: str
    probability: float


class PredictResponse(BaseModel):
    request_id: int
    status: str
    charged: int
    balance: int
    predictions: list[EmailPredictionResponse]
    errors: list[ValidationErrorResponse]


class PredictionHistoryItem(BaseModel):
    id: int
    model_name: str
    status: str
    charged: int
    created_at: datetime
    predictions_count: int
    errors_count: int


class TransactionHistoryItem(BaseModel):
    id: int
    transaction_type: str
    amount: int
    prediction_request_id: int | None
    created_at: datetime
