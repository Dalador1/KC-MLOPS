import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_database_url() -> str:
    user = os.getenv("POSTGRES_USER", "ml_user")
    password = os.getenv("POSTGRES_PASSWORD", "ml_password")
    host = os.getenv("DATABASE_HOST", "database")
    port = os.getenv("DATABASE_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "ml_service")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"


engine = create_engine(build_database_url())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
