import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Define test database URL and set it on settings BEFORE importing app.main
TEST_DATABASE_URL = "sqlite:///:memory:"
from app.core.config import settings
settings.DATABASE_URL = TEST_DATABASE_URL

import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
import app.database.connection as db_conn
from app.main import app

# Create engine for testing
connect_args = {"check_same_thread": False}
test_engine = create_engine(TEST_DATABASE_URL, connect_args=connect_args)

# Override the global connection engine with our test engine
db_conn.engine = test_engine


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Test session setup creating/dropping tables per test."""
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """Test client fixture with database dependency overrides."""
    def get_session_override():
        return session

    app.dependency_overrides[db_conn.get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
