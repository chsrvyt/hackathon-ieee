"""Explicit response shapes. Only the fields listed here ever leave the API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .models import Alert, CondonationRequest, Department, Projection, Student, Subject, User


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def department(d: Department | None) -> dict | None:
    return None if d is None else {"id": d.id, "code": d.code, "name": d.name}


def user(u: User) -> dict:
    student = u.student
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "department": department(u.department),
        "student_id": student.id if student else None,
    }


def subject(s: Subject | None) -> dict | None:
    return None if s is None else {"id": s.id, "code": s.code, "name": s.name, "department_id": s.department_id}


def student(s: Student, overall: Projection | None = None) -> dict:
    data = {
        "id": s.id,
        "roll_number": s.roll_number,
        "name": s.name,
        "semester": s.semester,
        "department": department(s.department),
        "mentor": {"id": s.mentor.id, "name": s.mentor.name} if s.mentor else None,
        "has_account": s.user_id is not None,
    }
    data["analytics"] = projection(overall) if overall else None
    return data


def projection(p: Projection) -> dict:
    return {
        "classes_attended": p.classes_attended,
        "classes_conducted": p.classes_conducted,
        "current_percentage": num(p.current_percentage),
        "projected_percentage": num(p.projected_percentage),
        "target_percentage": num(p.target_percentage),
        "trend": p.trend,
        "risk_level": p.risk_level,
        "reason": p.reason,
        "recommended_action": p.recommended_action,
        "classes_required": p.classes_required,
        "recovery_possible": p.recovery_possible,
        "calculated_at": iso(p.calculated_at),
    }


def alert(a: Alert) -> dict:
    return {
        "id": a.id,
        "student_id": a.student_id,
        "kind": a.kind,
        "severity": a.severity,
        "message": a.message,
        "is_read": a.is_read,
        "created_at": iso(a.created_at),
    }


def condonation(r: CondonationRequest, risk_level: str | None = None) -> dict:
    s = r.student
    return {
        "id": r.id,
        "student": {
            "id": s.id,
            "roll_number": s.roll_number,
            "name": s.name,
            "department": s.department.code,
            "mentor": s.mentor.name if s.mentor else None,
        },
        "subject": subject(r.subject),
        "reason": r.reason,
        "status": r.status,
        "attendance_at_request": num(r.attendance_at_request),
        "current_risk_level": risk_level,
        "reviewed_by": {"id": r.reviewer.id, "name": r.reviewer.name, "role": r.reviewer.role} if r.reviewer else None,
        "review_comment": r.review_comment,
        "created_at": iso(r.created_at),
        "reviewed_at": iso(r.reviewed_at),
        "history": [
            {
                "from_status": e.from_status,
                "to_status": e.to_status,
                "actor": e.actor.name if e.actor else None,
                "actor_role": e.actor.role if e.actor else None,
                "comment": e.comment,
                "at": iso(e.created_at),
            }
            for e in r.events
        ],
    }
