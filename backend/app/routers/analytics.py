from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import and_, case, select

from ..analytics.engine import percent_to_ratio, recovery_plan
from ..analytics.service import analyze_students, refresh_projections
from ..authz import REPORT_ROLES, STAFF_ROLES, ensure_can_view_department, ensure_can_view_student, student_scope
from ..deps import DB, CurrentUser, require_roles
from ..errors import AppError, not_found
from ..models import Department, Projection, Student, User
from ..services import reports

router = APIRouter(tags=["analytics"])
Staff = Annotated[User, Depends(require_roles(*STAFF_ROLES))]
Reporter = Annotated[User, Depends(require_roles(*REPORT_ROLES))]


@router.get("/analytics/student/{student_id}")
def student_analytics(student_id: int, db: DB, user: CurrentUser) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    ensure_can_view_student(user, student)
    (result,) = analyze_students(db, [student])
    data = result.to_dict()
    data["student"] = {
        "id": student.id,
        "roll_number": student.roll_number,
        "name": student.name,
        "semester": student.semester,
        "department": {"id": student.department.id, "code": student.department.code, "name": student.department.name},
        "mentor": {"id": student.mentor.id, "name": student.mentor.name} if student.mentor else None,
    }
    return data


@router.get("/analytics/risk-students")
def risk_students(
    db: DB,
    user: Staff,
    level: Annotated[str, Query(max_length=40)] = "CRITICAL,WARNING",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    levels = [lvl.strip().upper() for lvl in level.split(",") if lvl.strip()]
    if not levels or any(lvl not in ("CRITICAL", "WARNING", "SAFE") for lvl in levels):
        raise AppError(422, "VALIDATION_ERROR", "level must be a comma separated list of CRITICAL, WARNING, SAFE.")
    severity = case({"CRITICAL": 0, "WARNING": 1}, value=Projection.risk_level, else_=2)
    rows = db.execute(
        select(Student, Projection)
        .join(Projection, and_(Projection.student_id == Student.id, Projection.subject_id.is_(None)))
        .where(student_scope(user), Projection.risk_level.in_(levels))
        .order_by(severity, Projection.projected_percentage.asc().nulls_last(), Student.roll_number)
        .limit(limit)
    ).all()
    return {"items": [reports.risk_row(s, p) for s, p in rows]}


@router.get("/analytics/overview")
def overview(db: DB, user: Staff) -> dict:
    scope = student_scope(user)
    data = reports.build_summary(db, scope)
    data["pending_condonations"] = reports.pending_condonations(db, scope)
    data["scope"] = {
        "role": user.role,
        "label": (
            "My assigned students"
            if user.role == "MENTOR"
            else f"{user.department.code} department"
            if user.role == "ADMIN" and user.department
            else "All departments"
        ),
    }
    if user.role == "ADMIN":
        data["recent_imports"] = reports.recent_imports(db)
    return data


@router.get("/analytics/department/{department_id}")
def department_analytics(department_id: int, db: DB, user: Reporter) -> dict:
    department = db.get(Department, department_id)
    if department is None:
        raise not_found("Department")
    ensure_can_view_department(user, department_id)
    return reports.department_report(db, department)


@router.get("/reports/department/{department_id}/export.csv")
def department_export(department_id: int, db: DB, user: Reporter) -> Response:
    department = db.get(Department, department_id)
    if department is None:
        raise not_found("Department")
    ensure_can_view_department(user, department_id)
    report = reports.department_report(db, department)
    return Response(
        reports.department_report_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="attendai_{department.code.lower()}_shortage_report.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/analytics/recovery")
def recovery_calculator(
    user: CurrentUser,
    attended: Annotated[int, Query(ge=0, le=100000)],
    conducted: Annotated[int, Query(ge=0, le=100000)],
    target: Annotated[Decimal, Query(gt=0, le=100)] = Decimal("75"),
    remaining: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> dict:
    """Stateless what-if calculator: minimum X with (A + X) / (C + X) >= T."""
    if attended > conducted:
        raise AppError(422, "VALIDATION_ERROR", "Classes attended cannot exceed classes conducted.")
    plan = recovery_plan(attended, conducted, percent_to_ratio(target), remaining)
    return {
        "attended": attended,
        "conducted": conducted,
        "target_percentage": float(target),
        "current_percentage": round(attended / conducted * 100, 2) if conducted else None,
        **plan.to_dict(),
    }


@router.post("/analytics/recompute")
def recompute(db: DB, user: Annotated[User, Depends(require_roles("ADMIN"))]) -> dict:
    ids = list(db.scalars(select(Student.id).where(student_scope(user))))
    changes = refresh_projections(db, ids)
    db.commit()
    return {"students_recomputed": len(ids), "risk_changes": [c.to_dict() for c in changes]}
