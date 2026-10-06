from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_, select

from .. import serializers
from ..authz import STAFF_ROLES, ensure_can_view_student, student_scope
from ..deps import DB, CurrentUser, require_roles
from ..errors import AppError, not_found
from ..models import RISK_LEVELS, Projection, Student, User

router = APIRouter(tags=["students"])

_SEVERITY_ORDER = case({"CRITICAL": 0, "WARNING": 1, "SAFE": 2, "NO_DATA": 3}, value=Projection.risk_level, else_=3)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/students")
def list_students(
    db: DB,
    user: Annotated[User, Depends(require_roles(*STAFF_ROLES))],
    search: Annotated[str | None, Query(max_length=80)] = None,
    risk: Annotated[str | None, Query(max_length=60, description="Comma separated risk levels")] = None,
    department_id: Annotated[int | None, Query(gt=0)] = None,
    sort: Literal["risk", "name", "roll", "current", "projected"] = "risk",
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    conditions = [student_scope(user)]
    if search:
        term = f"%{_escape_like(search.strip())}%"
        conditions.append(or_(Student.name.ilike(term, escape="\\"), Student.roll_number.ilike(term, escape="\\")))
    if risk:
        levels = [lvl.strip().upper() for lvl in risk.split(",") if lvl.strip()]
        invalid = [lvl for lvl in levels if lvl not in RISK_LEVELS]
        if invalid:
            raise AppError(422, "VALIDATION_ERROR", f"Unknown risk level(s): {', '.join(invalid)}")
        if "NO_DATA" in levels:
            conditions.append(or_(Projection.risk_level.in_(levels), Projection.id.is_(None)))
        else:
            conditions.append(Projection.risk_level.in_(levels))
    if department_id:
        conditions.append(Student.department_id == department_id)

    base = (
        select(Student, Projection)
        .outerjoin(Projection, and_(Projection.student_id == Student.id, Projection.subject_id.is_(None)))
        .where(*conditions)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    order = {
        "risk": (_SEVERITY_ORDER, Projection.projected_percentage.asc().nulls_last(), Student.roll_number),
        "name": (Student.name,),
        "roll": (Student.roll_number,),
        "current": (Projection.current_percentage.asc().nulls_last(), Student.roll_number),
        "projected": (Projection.projected_percentage.asc().nulls_last(), Student.roll_number),
    }[sort]
    rows = db.execute(base.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [serializers.student(s, p) for s, p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/students/{student_id}")
def get_student(student_id: int, db: DB, user: CurrentUser) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    ensure_can_view_student(user, student)
    overall = db.scalar(select(Projection).where(Projection.student_id == student.id, Projection.subject_id.is_(None)))
    return {"student": serializers.student(student, overall)}
