"""Condonation state machine: (new) -> PENDING -> APPROVED | REJECTED | WITHDRAWN. Terminal states are final."""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..analytics.engine import SEVERITY
from ..analytics.service import analyze_students
from ..authz import ensure_can_review
from ..errors import AppError, forbidden, not_found
from ..models import Alert, CondonationEvent, CondonationRequest, User, utcnow

log = logging.getLogger("attendai.condonation")


def submit_request(db: Session, user: User, reason: str, subject_id: int | None) -> tuple[CondonationRequest, str]:
    if user.role != "STUDENT":
        raise forbidden("Only students can submit condonation requests.")
    student = user.student
    if student is None:
        raise AppError(409, "NO_STUDENT_PROFILE", "Your account is not linked to a student record.")

    (analysis,) = analyze_students(db, [student])
    if subject_id is not None:
        considered = [a for s, a in analysis.subjects if s.id == subject_id]
        if not considered:
            raise AppError(422, "VALIDATION_ERROR", "You have no attendance recorded for that subject.")
    else:
        considered = [analysis.overall] + [a for _, a in analysis.subjects]
    # Early-warning policy: a request may be filed once attendance is at risk (WARNING/CRITICAL),
    # not only after the shortage has already happened.
    eligible = any(a.risk_level in ("WARNING", "CRITICAL") for a in considered)
    if not eligible:
        raise AppError(
            422,
            "NOT_ELIGIBLE",
            "Condonation requests are only available when attendance is at risk (WARNING or CRITICAL).",
        )
    subject_filter = (
        CondonationRequest.subject_id.is_(None) if subject_id is None else CondonationRequest.subject_id == subject_id
    )
    pending = db.scalar(
        select(CondonationRequest.id).where(
            CondonationRequest.student_id == student.id, CondonationRequest.status == "PENDING", subject_filter
        )
    )
    if pending:
        raise AppError(409, "DUPLICATE_PENDING", "You already have a pending request for this. Wait for a decision.")

    basis = considered[0]
    req = CondonationRequest(
        student_id=student.id,
        subject_id=subject_id,
        reason=reason,
        status="PENDING",
        attendance_at_request=(
            Decimal(str(round(float(basis.current * 100), 2))) if basis.current is not None else None
        ),
    )
    db.add(req)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "DUPLICATE_PENDING", "You already have a pending request for this.") from exc
    db.add(CondonationEvent(request_id=req.id, actor_user_id=user.id, from_status=None, to_status="PENDING"))
    if student.mentor_id:
        db.add(
            Alert(
                recipient_user_id=student.mentor_id,
                student_id=student.id,
                kind="CONDONATION",
                severity="WARNING" if SEVERITY[analysis.risk_level] >= SEVERITY["WARNING"] else "INFO",
                message=f"New condonation request from {student.name} ({student.roll_number}) awaiting your review.",
            )
        )
    log.info("condonation created id=%s student_id=%s", req.id, student.id)
    return req, analysis.risk_level


def lock_request(db: Session, request_id: int) -> CondonationRequest:
    req = db.scalar(
        select(CondonationRequest).where(CondonationRequest.id == request_id).with_for_update(of=CondonationRequest)
    )
    if req is None:
        raise not_found("Condonation request")
    return req


def decide_request(db: Session, user: User, request_id: int, decision: str, comment: str | None) -> CondonationRequest:
    if user.role not in ("MENTOR", "ADMIN"):
        raise forbidden("Only the assigned mentor or an administrator can review condonation requests.")
    req = lock_request(db, request_id)
    ensure_can_review(user, req)
    if req.status != "PENDING":
        raise AppError(409, "INVALID_TRANSITION", f"This request is already {req.status} and cannot be changed.")
    comment = (comment or "").strip() or None
    if decision == "REJECTED" and (comment is None or len(comment) < 3):
        raise AppError(422, "VALIDATION_ERROR", "Please give a reason (comment) when rejecting a request.")
    previous = req.status
    req.status = decision
    req.reviewed_by = user.id
    req.review_comment = comment
    req.reviewed_at = utcnow()
    db.add(
        CondonationEvent(
            request_id=req.id, actor_user_id=user.id, from_status=previous, to_status=decision, comment=comment
        )
    )
    if req.student.user_id:
        subject = f" for {req.subject.name}" if req.subject else ""
        db.add(
            Alert(
                recipient_user_id=req.student.user_id,
                student_id=req.student_id,
                kind="CONDONATION",
                severity="INFO" if decision == "APPROVED" else "WARNING",
                message=(
                    f"Your condonation request{subject} was {decision.lower()} by {user.name}."
                    + (f" Comment: {comment}" if comment else "")
                ),
            )
        )
    log.info("condonation decided id=%s decision=%s reviewer_id=%s", req.id, decision, user.id)
    return req


def withdraw_request(db: Session, user: User, request_id: int) -> CondonationRequest:
    req = lock_request(db, request_id)
    if user.role != "STUDENT" or req.student.user_id != user.id:
        raise forbidden("Only the student who submitted the request can withdraw it.")
    if req.status != "PENDING":
        raise AppError(409, "INVALID_TRANSITION", f"This request is already {req.status} and cannot be withdrawn.")
    req.status = "WITHDRAWN"
    db.add(CondonationEvent(request_id=req.id, actor_user_id=user.id, from_status="PENDING", to_status="WITHDRAWN"))
    return req
