from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    balance: Mapped["CreditBalanceORM"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    transactions: Mapped[list["TransactionORM"]] = relationship(back_populates="user")
    prediction_requests: Mapped[list["PredictionRequestORM"]] = relationship(back_populates="user")


class CreditBalanceORM(Base):
    __tablename__ = "credit_balances"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[UserORM] = relationship(back_populates="balance")


class SpamModelORM(Base):
    __tablename__ = "spam_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    cost_per_email: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    prediction_requests: Mapped[list["PredictionRequestORM"]] = relationship(back_populates="model")


class PredictionRequestORM(Base):
    __tablename__ = "prediction_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("spam_models.id"), index=True)
    status: Mapped[str] = mapped_column(String(50))
    charged: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped[UserORM] = relationship(back_populates="prediction_requests")
    model: Mapped[SpamModelORM] = relationship(back_populates="prediction_requests")
    predictions: Mapped[list["EmailPredictionORM"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    validation_errors: Mapped[list["ValidationErrorORM"]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["TransactionORM"]] = relationship(back_populates="prediction_request")


class EmailPredictionORM(Base):
    __tablename__ = "email_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("prediction_requests.id"), index=True)
    subject: Mapped[str] = mapped_column(String(500))
    body: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(String(20))
    probability: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped[PredictionRequestORM] = relationship(back_populates="predictions")


class ValidationErrorORM(Base):
    __tablename__ = "validation_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("prediction_requests.id"), index=True)
    row: Mapped[int] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(String(500))

    request: Mapped[PredictionRequestORM] = relationship(back_populates="validation_errors")


class TransactionORM(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("user_id", "transaction_type", "amount", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(50))
    prediction_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("prediction_requests.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped[UserORM] = relationship(back_populates="transactions")
    prediction_request: Mapped[PredictionRequestORM | None] = relationship(
        back_populates="transactions"
    )
