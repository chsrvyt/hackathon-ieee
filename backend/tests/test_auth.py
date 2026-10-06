"""AUTH-01..05 plus session, CSRF and throttling behaviour."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.config import get_settings
from app.models import AuthSession, User

from .conftest import CSRF, make_client


def test_auth01_valid_login_sets_httponly_cookie(anon):
    r = anon.post("/api/auth/login", json={"email": "student@attendai.demo", "password": "Demo@2026"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["student_id"] is not None
    assert "password" not in str(body).lower()
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert anon.get("/api/auth/me").json()["user"]["email"] == "student@attendai.demo"


def test_login_email_is_case_insensitive(anon):
    r = anon.post("/api/auth/login", json={"email": "  Student@AttendAI.demo ", "password": "Demo@2026"})
    assert r.status_code == 200


def test_auth02_invalid_password_rejected(anon):
    r = anon.post("/api/auth/login", json={"email": "student@attendai.demo", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    unknown = anon.post("/api/auth/login", json={"email": "nobody@attendai.demo", "password": "wrong"})
    assert unknown.status_code == 401
    assert unknown.json()["error"]["message"] == r.json()["error"]["message"]  # no account enumeration


def test_auth03_unauthenticated_access_rejected(anon):
    for path in (
        "/api/auth/me",
        "/api/students",
        "/api/analytics/overview",
        "/api/analytics/student/1",
        "/api/alerts",
        "/api/condonation/pending",
        "/api/analytics/department/1",
    ):
        r = anon.get(path)
        assert r.status_code == 401, path
        assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_auth04_logout_invalidates_server_session(student):
    token = student.cookies.get(get_settings().session_cookie_name)
    assert student.post("/api/auth/logout").status_code == 200
    replay = make_client()
    replay.cookies.set(get_settings().session_cookie_name, token)
    r = replay.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "SESSION_EXPIRED"


def test_expired_session_rejected(student, db):
    db.execute(update(AuthSession).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
    db.commit()
    assert student.get("/api/auth/me").status_code == 401


def test_disabled_account_cannot_use_session(student, db):
    db.execute(update(User).where(User.email == "student@attendai.demo").values(is_active=False))
    db.commit()
    assert student.get("/api/auth/me").status_code == 401


def test_passwords_and_tokens_are_not_stored_in_plaintext(student, db):
    user = db.scalar(select(User).where(User.email == "student@attendai.demo"))
    assert user.password_hash.startswith("scrypt$") and "Demo@2026" not in user.password_hash
    token = student.cookies.get(get_settings().session_cookie_name)
    assert db.scalar(select(AuthSession.id).where(AuthSession.token_hash == token)) is None


def test_login_throttled_after_repeated_failures(anon):
    for _ in range(get_settings().login_max_failures):
        anon.post("/api/auth/login", json={"email": "admin@attendai.demo", "password": "nope"})
    r = anon.post("/api/auth/login", json={"email": "admin@attendai.demo", "password": "Demo@2026"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


def test_state_changing_request_without_csrf_header_rejected(student):
    r = student.post("/api/auth/logout", headers={"X-Requested-With": ""})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_login_validation_error_contract(anon):
    r = anon.post("/api/auth/login", json={"email": "x"}, headers=CSRF)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_session_probe_is_anonymous_friendly(anon, student):
    assert anon.get("/api/auth/session").json() == {"user": None}
    assert student.get("/api/auth/session").json()["user"]["role"] == "STUDENT"


def test_demo_accounts_listing(anon):
    body = anon.get("/api/auth/demo-accounts").json()
    assert body["enabled"] is True
    roles = {a["role"] for a in body["accounts"]}
    assert roles == {"ADMIN", "MENTOR", "STUDENT", "EXAM_CELL"}
