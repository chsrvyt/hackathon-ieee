"""Integration test fixtures: a real PostgreSQL database, migrated with Alembic and reseeded per test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://attendai:attendai@localhost:5432/attendai_test")
os.environ["APP_ENV"] = "test"
os.environ["DEMO_MODE"] = "true"
os.environ.setdefault("LOG_LEVEL", "WARNING")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.auth import throttle  # noqa: E402
from app.seed import seed  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
SAMPLE_CSV = BACKEND.parent / "sample_data" / "attendance_sample.csv"
PASSWORD = get_settings().demo_password
CSRF = {"X-Requested-With": "AttendAI"}


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def demo_data():
    """Fresh demo dataset for every test (wipes all tables first)."""
    throttle._failures.clear()
    db = SessionLocal()
    try:
        seed(db, reset=True)
    finally:
        db.close()


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def make_client(email: str | None = None, password: str = PASSWORD) -> TestClient:
    client = TestClient(app, headers=CSRF)
    if email:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
    return client


@pytest.fixture
def anon() -> TestClient:
    return make_client()


@pytest.fixture
def admin() -> TestClient:
    return make_client("admin@attendai.demo")


@pytest.fixture
def hod_ece() -> TestClient:
    return make_client("hod.ece@attendai.demo")


@pytest.fixture
def mentor() -> TestClient:
    return make_client("mentor@attendai.demo")


@pytest.fixture
def mentor_ece() -> TestClient:
    return make_client("mentor.ece@attendai.demo")


@pytest.fixture
def exam_cell() -> TestClient:
    return make_client("examcell@attendai.demo")


@pytest.fixture
def student() -> TestClient:
    """Rohan Verma, S003 (CSE)."""
    return make_client("student@attendai.demo")


def student_id(db, roll: str) -> int:
    from sqlalchemy import select

    from app.models import Student

    return db.scalar(select(Student.id).where(Student.roll_number == roll))


def upload(client: TestClient, content: bytes, filename: str = "attendance.csv", **form):
    data = {k: str(v).lower() if isinstance(v, bool) else v for k, v in form.items()}
    return client.post("/api/attendance/upload", files={"file": (filename, content)}, data=data)


def sample_bytes() -> bytes:
    return SAMPLE_CSV.read_bytes()
