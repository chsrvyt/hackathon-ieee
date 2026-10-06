"""Condonation workflow endpoints. Business rules live in services/condonation.py."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import serializers
from ..authz import STAFF_ROLES, ensure_can_view_student, student_scope
from ..deps import DB, CurrentUser, require_roles
from ..errors import not_found
from ..models import CondonationRequest, Projection, Student, User
from ..schemas import CondonationCreate, CondonationDecision
from ..services.condonation import decide_request, submit_request, withdraw_request

router = APIRouter(prefix="/condonation", tags=["condonation"])
Staff = Annotated[User, Depends(require_roles(*STAFF_ROLES))]


def _serialize_many(db: Session, requests: list[CondonationRequest]) -> list[dict]:
    ids = list({r.student_id for r in requests})
    levels = (
        dict(
            db.execute(
                select(Projection.student_id, Projection.risk_level).where(
                    Projection.student_id.in_(ids), Projection.subject_id.is_(None)
                )
            ).all()
        )
        if ids
        else {}
    )
    return [serializers.condonation(r, levels.get(r.student_id)) for r in requests]


@router.post("", status_code=201)
def create_request(body: CondonationCreate, db: DB, user: CurrentUser) -> dict:
    req, risk_level = submit_request(db, user, body.reason, body.subject_id)
    db.commit()
    db.refresh(req)
    return {"request": serializers.condonation(req, risk_level)}


@router.get("/student/{student_id}")
def student_requests(student_id: int, db: DB, user: CurrentUser) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    ensure_can_view_student(user, student)
    requests = list(
        db.scalars(
            select(CondonationRequest)
            .where(CondonationRequest.student_id == student.id)
            .order_by(CondonationRequest.created_at.desc(), CondonationRequest.id.desc())
        )
    )
    return {"items": _serialize_many(db, requests)}


@router.get("/pending")
def pending_requests(db: DB, user: Staff) -> dict:
    return list_requests(db, user, status="PENDING")


@router.get("")
def list_requests(
    db: DB,
    user: Staff,
    status: Literal["PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "ALL"] = "ALL",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict:
    query = (
        select(CondonationRequest).join(Student, Student.id == CondonationRequest.student_id).where(student_scope(user))
    )
    if status != "ALL":
        query = query.where(CondonationRequest.status == status)
    requests = list(
        db.scalars(query.order_by(CondonationRequest.created_at.desc(), CondonationRequest.id.desc()).limit(limit))
    )
    return {"items": _serialize_many(db, requests), "can_review": user.role in ("MENTOR", "ADMIN")}


@router.patch("/{request_id}/decision")
def decide(request_id: int, body: CondonationDecision, db: DB, user: CurrentUser) -> dict:
    req = decide_request(db, user, request_id, body.decision, body.comment)
    db.commit()
    db.refresh(req)
    return {"request": _serialize_many(db, [req])[0]}


@router.patch("/{request_id}/withdraw")
def withdraw(request_id: int, db: DB, user: CurrentUser) -> dict:
    req = withdraw_request(db, user, request_id)
    db.commit()
    db.refresh(req)
    return {"request": _serialize_many(db, [req])[0]}
