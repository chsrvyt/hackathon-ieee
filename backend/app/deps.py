from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .errors import AppError
from .models import AuthSession, User
from .security import hash_session_token

DB = Annotated[Session, Depends(get_db)]


def session_token(request: Request) -> str | None:
    """Bearer token (mobile app) or session cookie (web)."""
    auth = request.headers.get("authorization", "")
    scheme, _, value = auth.partition(" ")
    if scheme.lower() == "bearer" and value.strip():
        return value.strip()
    return request.cookies.get(get_settings().session_cookie_name)


def get_current_user(request: Request, db: DB) -> User:
    token = session_token(request)
    if not token:
        raise AppError(401, "UNAUTHENTICATED", "Please sign in to continue.")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_session_token(token)))
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AppError(401, "SESSION_EXPIRED", "Your session has expired. Please sign in again.")
    user = session.user
    if not user.is_active:
        raise AppError(401, "UNAUTHENTICATED", "This account is disabled.")
    request.state.session_id = session.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[[User], User]:
    def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "Your role is not allowed to perform this action.")
        return user

    return _dependency
