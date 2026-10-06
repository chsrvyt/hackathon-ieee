from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError

from .. import serializers
from ..authz import STAFF_ROLES, ensure_can_view_student, student_scope
from ..config import get_settings
from ..deps import DB, CurrentUser, require_roles
from ..errors import AppError, not_found
from ..models import AttendanceRecord, Student, Subject, User
from ..services import reports
from ..services.importer import (
    TEMPLATE_CSV,
    FileRejected,
    ImportOptions,
    ImportResult,
    import_attendance,
    record_rejected_import,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])
log = logging.getLogger("attendai.import")
Admin = Annotated[User, Depends(require_roles("ADMIN"))]


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks, size = [], 0
    while chunk := await upload.read(64 * 1024):
        size += len(chunk)
        if size > limit:
            raise FileRejected([], 413)
        chunks.append(chunk)
    return b"".join(chunks)


def _rejected(result: ImportResult, status: int, message: str) -> JSONResponse:
    body = result.to_dict()
    body["error"] = {
        "code": "VALIDATION_ERROR" if status == 422 else "UPLOAD_REJECTED",
        "message": message,
        "details": body["errors"],
    }
    return JSONResponse(status_code=status, content=body)


@router.post("/upload")
async def upload_attendance(
    db: DB,
    user: Admin,
    file: Annotated[UploadFile, File(description="CSV or XLSX attendance file")],
    mode: Annotated[Literal["strict", "replace"], Form()] = "strict",
    register_new: Annotated[bool, Form()] = False,
    dry_run: Annotated[bool, Form()] = False,
):
    settings = get_settings()
    options = ImportOptions(mode=mode, register_new=register_new, dry_run=dry_run)
    filename = file.filename or "upload"
    try:
        data = await _read_limited(file, settings.max_upload_bytes)
    except FileRejected:
        result = ImportResult(False, filename[-120:], "", mode)
        return _rejected(result, 413, f"The file exceeds the {settings.max_upload_mb:g} MB upload limit.")

    try:
        result = import_attendance(db, user, filename, data, options)
    except FileRejected as exc:
        db.rollback()
        result = ImportResult(False, filename[-120:], "", mode, errors=exc.issues)
        log.info("upload rejected (file-level) user_id=%s", user.id)
        return _rejected(result, exc.status_code, exc.issues[0].message if exc.issues else "File rejected.")
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "CONFLICT", "The data changed while importing (concurrent upload). Please retry.") from exc

    if not result.success:
        db.rollback()
        if not dry_run:
            record_rejected_import(db, user, result)
        log.info("upload rejected user_id=%s errors=%s", user.id, len(result.errors))
        n = len(result.errors)
        return _rejected(
            result,
            422,
            f"The file was rejected: {n} problem{'s' if n != 1 else ''} found. No records were changed.",
        )
    if dry_run:
        db.rollback()
    else:
        db.commit()
    log.info("upload ok user_id=%s rows=%s dry_run=%s", user.id, result.rows_processed, dry_run)
    return result.to_dict()


@router.get("/template.csv")
def template(user: CurrentUser) -> PlainTextResponse:
    return PlainTextResponse(
        TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="attendai_attendance_template.csv"'},
    )


@router.get("/imports")
def list_imports(db: DB, user: Admin) -> dict:
    return {"items": reports.recent_imports(db, limit=20)}


@router.get("/student/{student_id}")
def student_attendance(student_id: int, db: DB, user: CurrentUser) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise not_found("Student")
    ensure_can_view_student(user, student)
    rows = db.execute(
        select(AttendanceRecord, Subject)
        .join(Subject, Subject.id == AttendanceRecord.subject_id)
        .where(AttendanceRecord.student_id == student.id)
        .order_by(AttendanceRecord.date, Subject.code)
    ).all()
    return {
        "student": serializers.student(student),
        "records": [
            {
                "id": r.id,
                "date": r.date.isoformat(),
                "subject": serializers.subject(s),
                "classes_conducted": r.classes_conducted,
                "classes_attended": r.classes_attended,
                "percentage": round(r.classes_attended / r.classes_conducted * 100, 2) if r.classes_conducted else None,
            }
            for r, s in rows
        ],
    }


@router.get("/subject/{subject_id}")
def subject_attendance(subject_id: int, db: DB, user: Annotated[User, Depends(require_roles(*STAFF_ROLES))]) -> dict:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise not_found("Subject")
    rows = db.execute(
        select(
            Student,
            func.sum(AttendanceRecord.classes_attended),
            func.sum(AttendanceRecord.classes_conducted),
        )
        .join(
            AttendanceRecord,
            and_(AttendanceRecord.student_id == Student.id, AttendanceRecord.subject_id == subject.id),
        )
        .where(student_scope(user))
        .group_by(Student.id)
        .order_by(Student.roll_number)
    ).all()
    return {
        "subject": serializers.subject(subject),
        "students": [
            {
                "id": s.id,
                "roll_number": s.roll_number,
                "name": s.name,
                "classes_attended": int(a),
                "classes_conducted": int(c),
                "percentage": round(int(a) / int(c) * 100, 2) if c else None,
            }
            for s, a, c in rows
        ],
    }
