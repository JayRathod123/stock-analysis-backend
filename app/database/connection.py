from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings

# If DATABASE_URL is SQLite, we need connect_args for multithreading compatibility in tests
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)


def init_db() -> None:
    """Initialize database tables from defined models."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency injection helper for database sessions."""
    with Session(engine) as session:
        yield session
