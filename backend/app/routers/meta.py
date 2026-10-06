from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select, text

from .. import serializers
from ..deps import DB, CurrentUser
from ..models import Department, Student, Subject

router = APIRouter(tags=["meta"])


def health_payload(db) -> tuple[int, dict]:
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health must never raise
        return 503, {"status": "error", "database": "unavailable"}
    return 200, {"status": "ok"}


@router.get("/version")
def version() -> dict:
    """Public: which commit is serving, so a pipeline can wait for a redeploy before testing it."""
    return {"commit": os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GIT_COMMIT") or None}


@router.get("/departments")
def departments(db: DB, user: CurrentUser) -> dict:
    query = select(Department).order_by(Department.code)
    if user.role == "ADMIN" and user.department_id is not None:
        query = query.where(Department.id == user.department_id)
    elif user.role == "MENTOR":
        query = query.where(Department.id.in_(select(Student.department_id).where(Student.mentor_id == user.id)))
    elif user.role == "STUDENT":
        query = query.where(Department.id.in_(select(Student.department_id).where(Student.user_id == user.id)))
    return {"items": [serializers.department(d) for d in db.scalars(query)]}


@router.get("/subjects")
def subjects(db: DB, user: CurrentUser, department_id: Annotated[int | None, Query(gt=0)] = None) -> dict:
    query = select(Subject).order_by(Subject.code)
    if department_id:
        query = query.where(Subject.department_id == department_id)
    return {"items": [serializers.subject(s) for s in db.scalars(query)]}
