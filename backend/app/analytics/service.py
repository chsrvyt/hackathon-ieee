"""Glue between the database and the pure analytics engine."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Alert, AttendanceRecord, Projection, Student, Subject, utcnow
from .engine import SEVERITY, Analysis, Period, Policy, aggregate_by_date, analyze, analyze_overall, as_percentage, fmt


def current_policy() -> Policy:
    s = get_settings()
    return Policy.from_percentages(
        s.target_percentage, s.warning_band_points, s.trend_recent_periods, s.trend_threshold_points
    )


def planned_for(subject: Subject) -> int:
    return subject.planned_classes or get_settings().default_planned_classes


def _dec(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def load_periods(db: Session, student_ids: Sequence[int]) -> dict[int, dict[int, list[Period]]]:
    """student_id -> subject_id -> periods (sorted by date)."""
    result: dict[int, dict[int, list[Period]]] = defaultdict(lambda: defaultdict(list))
    if not student_ids:
        return result
    rows = db.execute(
        select(
            AttendanceRecord.student_id,
            AttendanceRecord.subject_id,
            AttendanceRecord.date,
            AttendanceRecord.classes_conducted,
            AttendanceRecord.classes_attended,
        )
        .where(AttendanceRecord.student_id.in_(student_ids))
        .order_by(AttendanceRecord.date)
    )
    for sid, subj, d, c, a in rows:
        result[sid][subj].append(Period(d, c, a))
    return result


@dataclass
class StudentAnalysis:
    student: Student
    overall: Analysis
    subjects: list[tuple[Subject, Analysis]]
    periods: dict[int, list[Period]]

    @property
    def risk_level(self) -> str:
        levels = [self.overall.risk_level] + [a.risk_level for _, a in self.subjects]
        if self.overall.risk_level == "NO_DATA":
            return "NO_DATA"
        return max(levels, key=lambda lvl: SEVERITY[lvl])

    def _driver(self) -> tuple[str, Analysis]:
        """The analysis that determines the student's overall level (overall wins ties)."""
        level = self.risk_level
        if self.overall.risk_level == level:
            return "Overall", self.overall
        worst_subjects = [(s, a) for s, a in self.subjects if a.risk_level == level]
        worst_subjects.sort(key=lambda sa: sa[1].projected or 0)
        subject, analysis = worst_subjects[0]
        return subject.name, analysis

    @property
    def reason(self) -> str:
        label, driver = self._driver()
        if label == "Overall":
            text = driver.reason
            flagged = [s.name for s, a in self.subjects if SEVERITY[a.risk_level] >= SEVERITY["WARNING"]]
            if flagged and self.risk_level != "SAFE":
                text += f" Subjects needing attention: {', '.join(flagged)}."
            return text
        return (
            f"Overall attendance is {self.overall.risk_level.lower()} "
            f"({fmt(self.overall.projected)} projected), but {label} is "
            f"{driver.risk_level}: {driver.reason}"
        )

    @property
    def recommended_action(self) -> str:
        label, driver = self._driver()
        return driver.recommended_action if label == "Overall" else f"{label}: {driver.recommended_action}"

    def to_dict(self) -> dict:
        overall = self.overall.to_dict()
        timeline = []
        cum_c = cum_a = 0
        all_periods = [p for ps in self.periods.values() for p in ps]
        for p in aggregate_by_date(all_periods):
            cum_c += p.conducted
            cum_a += p.attended
            timeline.append(
                {
                    "date": p.date.isoformat(),
                    "conducted": p.conducted,
                    "attended": p.attended,
                    "period_percentage": round(p.attended / p.conducted * 100, 2) if p.conducted else None,
                    "cumulative_percentage": round(cum_a / cum_c * 100, 2) if cum_c else None,
                }
            )
        subjects = []
        for subject, analysis in self.subjects:
            item = analysis.to_dict()
            item["subject"] = {"id": subject.id, "code": subject.code, "name": subject.name}
            subjects.append(item)
        return {
            "student_id": self.student.id,
            "current_percentage": overall["current_percentage"],
            "projected_percentage": overall["projected_percentage"],
            "target_percentage": overall["target_percentage"],
            "risk_level": self.risk_level,
            "trend": overall["trend"],
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "recovery": overall["recovery"],
            "overall": overall,
            "subjects": subjects,
            "timeline": timeline,
            "policy": {
                "target_percentage": as_percentage(self.overall.policy.target),
                "warning_band_points": as_percentage(self.overall.policy.warning_band),
                "trend_recent_periods": self.overall.policy.trend_recent_periods,
                "trend_threshold_points": as_percentage(self.overall.policy.trend_threshold),
            },
            "disclaimer": (
                "Decision-support estimate based on recorded attendance and the stated assumptions. "
                "It is not a guarantee of future attendance or an examination-eligibility ruling."
            ),
        }


def analyze_students(db: Session, students: Sequence[Student], policy: Policy | None = None) -> list[StudentAnalysis]:
    policy = policy or current_policy()
    periods_by_student = load_periods(db, [s.id for s in students])
    subject_ids = {sub for per in periods_by_student.values() for sub in per}
    subjects = {s.id: s for s in db.scalars(select(Subject).where(Subject.id.in_(subject_ids)))} if subject_ids else {}
    results = []
    for student in students:
        per_subject = periods_by_student.get(student.id, {})
        subject_results: list[tuple[Subject, Analysis]] = []
        planned_total = remaining_total = 0
        for subject_id in sorted(per_subject, key=lambda sid: subjects[sid].code):
            subject = subjects[subject_id]
            planned = planned_for(subject)
            analysis = analyze(subject.name, per_subject[subject_id], planned, policy)
            planned_total += planned
            remaining_total += analysis.remaining_classes
            subject_results.append((subject, analysis))
        all_periods = [p for ps in per_subject.values() for p in ps]
        overall = analyze_overall("Overall", all_periods, planned_total, remaining_total, policy)
        results.append(StudentAnalysis(student, overall, subject_results, dict(per_subject)))
    return results


def _projection_row(student_id: int, subject_id: int | None, a: Analysis, level: str, reason: str, action: str):
    return Projection(
        student_id=student_id,
        subject_id=subject_id,
        classes_attended=a.attended,
        classes_conducted=a.conducted,
        current_percentage=_dec(as_percentage(a.current)),
        projected_percentage=_dec(as_percentage(a.projected)),
        target_percentage=_dec(as_percentage(a.policy.target)),
        trend=a.trend.direction,
        risk_level=level,
        reason=reason,
        recommended_action=action,
        classes_required=a.recovery.classes_required,
        recovery_possible=a.recovery.possible,
        calculated_at=utcnow(),
    )


@dataclass
class RiskChange:
    student_id: int
    roll_number: str
    name: str
    previous: str | None
    current: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def refresh_projections(db: Session, student_ids: Iterable[int], create_alerts: bool = True) -> list[RiskChange]:
    """Recompute and persist the latest analytics snapshot for the given students.

    Runs inside the caller's transaction so an import and its analytics commit atomically.
    """
    ids = sorted(set(student_ids))
    changes: list[RiskChange] = []
    policy = current_policy()
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        students = list(db.scalars(select(Student).where(Student.id.in_(chunk)).order_by(Student.id)))
        previous = dict(
            db.execute(
                select(Projection.student_id, Projection.risk_level).where(
                    Projection.student_id.in_(chunk), Projection.subject_id.is_(None)
                )
            ).all()
        )
        db.execute(delete(Projection).where(Projection.student_id.in_(chunk)))
        for sa in analyze_students(db, students, policy):
            level = sa.risk_level
            db.add(_projection_row(sa.student.id, None, sa.overall, level, sa.reason, sa.recommended_action))
            for subject, analysis in sa.subjects:
                db.add(
                    _projection_row(
                        sa.student.id,
                        subject.id,
                        analysis,
                        analysis.risk_level,
                        analysis.reason,
                        analysis.recommended_action,
                    )
                )
            prev = previous.get(sa.student.id)
            if prev != level:
                changes.append(RiskChange(sa.student.id, sa.student.roll_number, sa.student.name, prev, level))
                if create_alerts:
                    _risk_alerts(db, sa, prev, level)
    db.flush()
    return changes


def _risk_alerts(db: Session, sa: StudentAnalysis, previous: str | None, level: str) -> None:
    student = sa.student
    proj = fmt(sa.overall.projected)
    target = fmt(sa.overall.policy.target)
    if level in ("WARNING", "CRITICAL"):
        if student.user_id:
            db.add(
                Alert(
                    recipient_user_id=student.user_id,
                    student_id=student.id,
                    kind="RISK",
                    severity=level,
                    message=f"Attendance risk is now {level}. {sa.reason} Next step: {sa.recommended_action}",
                )
            )
        if student.mentor_id:
            db.add(
                Alert(
                    recipient_user_id=student.mentor_id,
                    student_id=student.id,
                    kind="RISK",
                    severity=level,
                    message=(
                        f"{student.name} ({student.roll_number}) is now {level}"
                        f"{f' (was {previous})' if previous and previous != 'NO_DATA' else ''}: "
                        f"overall {fmt(sa.overall.current)} now, {proj} projected vs {target} target."
                    ),
                )
            )
    elif level == "SAFE" and previous in ("WARNING", "CRITICAL") and student.user_id:
        db.add(
            Alert(
                recipient_user_id=student.user_id,
                student_id=student.id,
                kind="RISK",
                severity="INFO",
                message=f"Good news: your attendance risk improved from {previous} to SAFE ({proj} projected).",
            )
        )
