"""Aggregated reporting built from the persisted projection snapshots (fast, indexed)."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, and_, func, select
from sqlalchemy.orm import Session

from ..analytics.engine import SEVERITY
from ..analytics.service import current_policy
from ..models import AttendanceImport, CondonationRequest, Department, Projection, Student, Subject, User
from ..serializers import iso, num

HISTOGRAM_BUCKETS = [(0, 50), (50, 65), (65, 75), (75, 85), (85, 95), (95, 100.01)]


def _pct(attended: int, conducted: int) -> float | None:
    return round(attended / conducted * 100, 2) if conducted else None


def _bucket_label(lo: float, hi: float) -> str:
    return f"{lo:g}–{min(hi, 100):g}%" if hi <= 100 else f"{lo:g}–100%"


def build_summary(db: Session, scope: ColumnElement[bool], at_risk_limit: int = 10) -> dict:
    target = Decimal(str(current_policy().target * 100))
    rows = db.execute(
        select(Student, Projection)
        .outerjoin(Projection, and_(Projection.student_id == Student.id, Projection.subject_id.is_(None)))
        .where(scope)
    ).all()

    risk = Counter({"CRITICAL": 0, "WARNING": 0, "SAFE": 0, "NO_DATA": 0})
    histogram = Counter()
    tot_a = tot_c = shortage = 0
    dept_stats: dict[int, dict] = {}
    at_risk = []
    for student, proj in rows:
        level = proj.risk_level if proj else "NO_DATA"
        risk[level] += 1
        d = dept_stats.setdefault(
            student.department_id,
            {
                "department": {
                    "id": student.department.id,
                    "code": student.department.code,
                    "name": student.department.name,
                },
                "students": 0,
                "attended": 0,
                "conducted": 0,
                "shortage": 0,
                "risk": Counter({"CRITICAL": 0, "WARNING": 0, "SAFE": 0, "NO_DATA": 0}),
            },
        )
        d["students"] += 1
        d["risk"][level] += 1
        if proj and proj.classes_conducted:
            tot_a += proj.classes_attended
            tot_c += proj.classes_conducted
            d["attended"] += proj.classes_attended
            d["conducted"] += proj.classes_conducted
            cur = float(proj.current_percentage)
            for lo, hi in HISTOGRAM_BUCKETS:
                if lo <= cur < hi:
                    histogram[_bucket_label(lo, hi)] += 1
                    break
            if proj.current_percentage < target:
                shortage += 1
                d["shortage"] += 1
        if level in ("CRITICAL", "WARNING"):
            at_risk.append((student, proj))

    at_risk.sort(key=lambda sp: (-SEVERITY[sp[1].risk_level], float(sp[1].projected_percentage or 0)))
    subject_rows = db.execute(
        select(
            Subject,
            func.count(Projection.id),
            func.sum(Projection.classes_attended),
            func.sum(Projection.classes_conducted),
            func.count(Projection.id).filter(Projection.current_percentage < target),
            func.count(Projection.id).filter(Projection.risk_level == "CRITICAL"),
            func.count(Projection.id).filter(Projection.risk_level == "WARNING"),
        )
        .join(Projection, Projection.subject_id == Subject.id)
        .join(Student, Student.id == Projection.student_id)
        .where(scope)
        .group_by(Subject.id)
        .order_by(Subject.code)
    ).all()
    subjects = [
        {
            "subject": {"id": s.id, "code": s.code, "name": s.name, "department": s.department.code},
            "students": n,
            "average_percentage": _pct(int(a or 0), int(c or 0)),
            "below_target": below,
            "critical": crit,
            "warning": warn,
        }
        for s, n, a, c, below, crit, warn in subject_rows
    ]

    return {
        "target_percentage": float(target),
        "total_students": len(rows),
        "students_with_data": len(rows) - risk["NO_DATA"],
        "average_percentage": _pct(tot_a, tot_c),
        "shortage_count": shortage,
        "risk_distribution": dict(risk),
        "attendance_histogram": [
            {"bucket": _bucket_label(lo, hi), "count": histogram[_bucket_label(lo, hi)]} for lo, hi in HISTOGRAM_BUCKETS
        ],
        "departments": [
            {
                "department": d["department"],
                "students": d["students"],
                "average_percentage": _pct(d["attended"], d["conducted"]),
                "shortage_count": d["shortage"],
                "risk_distribution": dict(d["risk"]),
            }
            for d in sorted(dept_stats.values(), key=lambda x: x["department"]["code"])
        ],
        "subjects": subjects,
        "at_risk_students": [risk_row(s, p) for s, p in at_risk[:at_risk_limit]],
        "at_risk_total": len(at_risk),
    }


def risk_row(student: Student, proj: Projection) -> dict:
    return {
        "id": student.id,
        "roll_number": student.roll_number,
        "name": student.name,
        "department": student.department.code,
        "semester": student.semester,
        "mentor": student.mentor.name if student.mentor else None,
        "current_percentage": num(proj.current_percentage),
        "projected_percentage": num(proj.projected_percentage),
        "trend": proj.trend,
        "risk_level": proj.risk_level,
        "reason": proj.reason,
        "recommended_action": proj.recommended_action,
        "classes_required": proj.classes_required,
        "recovery_possible": proj.recovery_possible,
    }


def pending_condonations(db: Session, scope: ColumnElement[bool]) -> int:
    return (
        db.scalar(
            select(func.count(CondonationRequest.id))
            .join(Student, Student.id == CondonationRequest.student_id)
            .where(scope, CondonationRequest.status == "PENDING")
        )
        or 0
    )


def recent_imports(db: Session, user: User, limit: int = 5) -> list[dict]:
    query = select(AttendanceImport).order_by(AttendanceImport.id.desc()).limit(limit)
    if user.department_id is not None:  # a department HOD only sees their own uploads
        query = query.where(AttendanceImport.uploaded_by == user.id)
    imports = db.scalars(query)
    return [
        {
            "id": i.id,
            "filename": i.filename,
            "file_type": i.file_type,
            "mode": i.mode,
            "status": i.status,
            "rows_total": i.rows_total,
            "rows_inserted": i.rows_inserted,
            "rows_updated": i.rows_updated,
            "rows_rejected": i.rows_rejected,
            "uploaded_by": i.uploader.name if i.uploader else None,
            "created_at": iso(i.created_at),
        }
        for i in imports
    ]


def shortage_list(db: Session, department_id: int) -> list[dict]:
    """Every student in the department below target overall or in any subject, with subject detail."""
    target = Decimal(str(current_policy().target * 100))
    rows = db.execute(
        select(Student, Projection)
        .join(Projection, Projection.student_id == Student.id)
        .where(Student.department_id == department_id)
        .order_by(Student.roll_number)
    ).all()
    by_student: dict[int, dict] = {}
    subj_flags: dict[int, list] = defaultdict(list)
    for student, proj in rows:
        entry = by_student.setdefault(student.id, {"student": student, "overall": None})
        if proj.subject_id is None:
            entry["overall"] = proj
        elif proj.current_percentage is not None and proj.current_percentage < target:
            subj_flags[student.id].append(
                {
                    "code": proj.subject.code,
                    "name": proj.subject.name,
                    "current_percentage": num(proj.current_percentage),
                    "projected_percentage": num(proj.projected_percentage),
                    "risk_level": proj.risk_level,
                }
            )
    status = dict(
        db.execute(
            select(CondonationRequest.student_id, CondonationRequest.status)
            .join(Student, Student.id == CondonationRequest.student_id)
            .where(Student.department_id == department_id)
            .order_by(CondonationRequest.created_at)
        ).all()
    )
    out = []
    for sid, entry in by_student.items():
        overall = entry["overall"]
        if overall is None:
            continue
        below = overall is not None and overall.current_percentage is not None and overall.current_percentage < target
        if not below and not subj_flags[sid]:
            continue
        row = risk_row(entry["student"], overall)
        row["overall_below_target"] = below
        row["subjects_below_target"] = subj_flags[sid]
        row["latest_condonation_status"] = status.get(sid)
        out.append(row)
    out.sort(key=lambda r: r["current_percentage"] if r["current_percentage"] is not None else 101)
    return out


def department_report(db: Session, department: Department) -> dict:
    summary = build_summary(db, Student.department_id == department.id, at_risk_limit=50)
    summary["department"] = {"id": department.id, "code": department.code, "name": department.name}
    summary["shortage_students"] = shortage_list(db, department.id)
    summary["pending_condonations"] = pending_condonations(db, Student.department_id == department.id)
    summary["generated_at"] = iso(datetime.now(UTC))
    return summary


def _safe_cell(value: object) -> object:
    """Neutralise spreadsheet formula injection in exported CSV cells."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def department_report_csv(report: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            f"AttendAI department shortage report - {report['department']['code']}",
            f"generated {report['generated_at']}",
            f"target {report['target_percentage']}%",
        ]
    )
    writer.writerow([])
    writer.writerow(
        [
            "roll_number",
            "name",
            "semester",
            "mentor",
            "current_percentage",
            "projected_percentage",
            "trend",
            "risk_level",
            "subjects_below_target",
            "classes_required",
            "recovery_possible",
            "latest_condonation_status",
            "reason",
        ]
    )
    for r in report["shortage_students"]:
        subjects = "; ".join(f"{s['code']} {s['current_percentage']}%" for s in r["subjects_below_target"])
        writer.writerow(
            [
                _safe_cell(v)
                for v in (
                    r["roll_number"],
                    r["name"],
                    r["semester"],
                    r["mentor"] or "",
                    r["current_percentage"],
                    r["projected_percentage"],
                    r["trend"],
                    r["risk_level"],
                    subjects,
                    r["classes_required"],
                    r["recovery_possible"],
                    r["latest_condonation_status"] or "",
                    r["reason"],
                )
            ]
        )
    return buf.getvalue()
