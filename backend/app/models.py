"""SQLAlchemy ORM models. Integrity rules are enforced in the database, not only in code."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("STUDENT", "MENTOR", "ADMIN", "EXAM_CELL")
RISK_LEVELS = ("SAFE", "WARNING", "CRITICAL", "NO_DATA")
TRENDS = ("IMPROVING", "STABLE", "DECREASING", "INSUFFICIENT_DATA")
CONDONATION_STATUSES = ("PENDING", "APPROVED", "REJECTED", "WITHDRAWN")
ALERT_SEVERITIES = ("INFO", "WARNING", "CRITICAL")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(_in("role", ROLES), name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    # For ADMIN this is the HOD scope (NULL = institution-wide). Informational for other roles.
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    department: Mapped[Department | None] = relationship(lazy="joined")
    student: Mapped[Student | None] = relationship(
        back_populates="user", foreign_keys="Student.user_id", uselist=False, lazy="selectin"
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="joined")


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (CheckConstraint("semester BETWEEN 1 AND 12", name="ck_students_semester"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), unique=True)
    roll_number: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    semester: Mapped[int] = mapped_column(SmallInteger)
    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User | None] = relationship(back_populates="student", foreign_keys=[user_id])
    mentor: Mapped[User | None] = relationship(foreign_keys=[mentor_id], lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (CheckConstraint("planned_classes IS NULL OR planned_classes > 0", name="ck_subjects_planned"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    # Total classes scheduled for the semester; drives the "remaining classes" projection input.
    planned_classes: Mapped[int | None] = mapped_column(Integer)

    department: Mapped[Department] = relationship(lazy="joined")


class AttendanceImport(Base):
    __tablename__ = "attendance_imports"
    __table_args__ = (CheckConstraint(_in("status", ("COMPLETED", "REJECTED")), name="ck_imports_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(8))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    uploader: Mapped[User | None] = relationship(lazy="joined")


class AttendanceRecord(Base):
    """Classes conducted/attended for one student in one subject for the period ending on `date`."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "date", name="uq_attendance_student_subject_date"),
        CheckConstraint("classes_conducted >= 0", name="ck_attendance_conducted_nonneg"),
        CheckConstraint("classes_attended >= 0", name="ck_attendance_attended_nonneg"),
        CheckConstraint("classes_attended <= classes_conducted", name="ck_attendance_attended_le_conducted"),
        Index("ix_attendance_student_date", "student_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), index=True)
    date: Mapped[date] = mapped_column(Date)
    classes_conducted: Mapped[int] = mapped_column(Integer)
    classes_attended: Mapped[int] = mapped_column(Integer)
    import_id: Mapped[int | None] = mapped_column(ForeignKey("attendance_imports.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Projection(Base):
    """Latest computed analytics per student (subject_id NULL = overall) and per subject.

    Recomputed transactionally whenever a student's attendance changes, so list views
    and dashboards read pre-computed, indexed rows instead of re-deriving everything.
    """

    __tablename__ = "projections"
    __table_args__ = (
        CheckConstraint(_in("risk_level", RISK_LEVELS), name="ck_projections_risk"),
        CheckConstraint(_in("trend", TRENDS), name="ck_projections_trend"),
        Index(
            "uq_projections_overall",
            "student_id",
            unique=True,
            postgresql_where=text("subject_id IS NULL"),
        ),
        Index(
            "uq_projections_subject",
            "student_id",
            "subject_id",
            unique=True,
            postgresql_where=text("subject_id IS NOT NULL"),
        ),
        Index("ix_projections_risk", "risk_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    classes_attended: Mapped[int] = mapped_column(Integer)
    classes_conducted: Mapped[int] = mapped_column(Integer)
    current_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    projected_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    target_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    trend: Mapped[str] = mapped_column(String(20))
    risk_level: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    classes_required: Mapped[int | None] = mapped_column(Integer)
    recovery_possible: Mapped[bool | None] = mapped_column(Boolean)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subject: Mapped[Subject | None] = relationship(lazy="joined")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(_in("severity", ALERT_SEVERITIES), name="ck_alerts_severity"),
        Index("ix_alerts_recipient", "recipient_user_id", "is_read", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CondonationRequest(Base):
    __tablename__ = "condonation_requests"
    __table_args__ = (
        CheckConstraint(_in("status", CONDONATION_STATUSES), name="ck_condonation_status"),
        # At most one open request per student per subject (subject NULL = overall).
        Index(
            "uq_condonation_one_pending",
            "student_id",
            text("COALESCE(subject_id, 0)"),
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("ix_condonation_status", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"))
    reason: Mapped[str] = mapped_column(Text)
    document_path: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    attendance_at_request: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[Student] = relationship(lazy="joined")
    subject: Mapped[Subject | None] = relationship(lazy="joined")
    reviewer: Mapped[User | None] = relationship(lazy="joined")
    events: Mapped[list[CondonationEvent]] = relationship(
        back_populates="request", order_by="CondonationEvent.id", lazy="selectin", cascade="all, delete-orphan"
    )


class CondonationEvent(Base):
    """Append-only audit trail of every condonation status transition."""

    __tablename__ = "condonation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("condonation_requests.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    from_status: Mapped[str | None] = mapped_column(String(10))
    to_status: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped[CondonationRequest] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship(lazy="joined")
