from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from .. import serializers
from ..config import get_settings
from ..deps import DB, CurrentUser, get_current_user
from ..errors import AppError
from ..models import AuthSession, User
from ..schemas import LoginRequest
from ..security import burn_password_check, hash_session_token, new_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("attendai.auth")


class LoginThrottle:
    """In-process sliding window of failed logins per (client IP, email)."""

    MAX_KEYS = 10_000

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float) -> deque[float]:
        q = self._failures[key]
        cutoff = time.monotonic() - window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str) -> bool:
        s = get_settings()
        with self._lock:
            return len(self._prune(key, s.login_window_minutes * 60)) >= s.login_max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())
            if len(self._failures) > self.MAX_KEYS:  # bound memory under credential spraying
                window = get_settings().login_window_minutes * 60
                for stale in [k for k in self._failures if not self._prune(k, window)]:
                    del self._failures[stale]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


throttle = LoginThrottle()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> dict:
    settings = get_settings()
    key = f"{_client_ip(request)}|{body.email}"
    if throttle.blocked(key):
        raise AppError(429, "RATE_LIMITED", "Too many failed sign-in attempts. Wait a few minutes and try again.")
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        burn_password_check(body.password)
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        throttle.fail(key)
        log.info("login failed")
        raise AppError(401, "INVALID_CREDENTIALS", "Incorrect email or password.")
    throttle.reset(key)

    token = new_session_token()
    now = datetime.now(UTC)
    ttl = timedelta(hours=settings.session_ttl_hours)
    db.add(AuthSession(user_id=user.id, token_hash=hash_session_token(token), created_at=now, expires_at=now + ttl))
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path="/",
    )
    log.info("login ok user_id=%s role=%s", user.id, user.role)
    return {"user": serializers.user(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: DB) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            db.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return {"success": True}


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return {"user": serializers.user(user)}


@router.get("/session")
def session(request: Request, db: DB) -> dict:
    """Like /me, but answers 200 with user=null for anonymous visitors (no console-noise 401 on page load)."""
    try:
        return {"user": serializers.user(get_current_user(request, db))}
    except AppError as exc:
        if exc.status_code == 401:
            return {"user": None}
        raise


@router.get("/demo-accounts")
def demo_accounts() -> dict:
    """Public list of demo logins, only when DEMO_MODE is enabled (never in a real deployment)."""
    settings = get_settings()
    if not settings.demo_mode:
        return {"enabled": False, "accounts": []}
    from ..seed import DEMO_ACCOUNTS

    return {
        "enabled": True,
        "password": settings.demo_password,
        "accounts": [{"role": a["role"], "email": a["email"], "label": a["label"]} for a in DEMO_ACCOUNTS],
    }
