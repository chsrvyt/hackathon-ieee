"""ATT-01..08: attendance import validation and transactional behaviour."""

import io

import openpyxl
import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import AttendanceImport, AttendanceRecord, Projection, Student, Subject

from .conftest import SAMPLE_CSV, sample_bytes, student_id, upload

HEADER = "student_roll,subject_code,date,classes_conducted,classes_attended\n"


def _count(db):
    return db.scalar(select(func.count(AttendanceRecord.id)))


def _messages(r):
    return " | ".join(e["message"] for e in r.json()["errors"])


def test_att01_valid_csv_imported_and_analytics_refreshed(admin, db):
    before = _count(db)
    r = upload(admin, sample_bytes(), "attendance_sample.csv")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["rows_processed"] == 24 and body["rows_rejected"] == 0 and body["errors"] == []
    assert body["rows_inserted"] == 24 and body["students_affected"] == 8
    assert _count(db) == before + 24
    changes = {c["roll_number"]: (c["previous"], c["current"]) for c in body["risk_changes"]}
    assert changes["S003"] == ("WARNING", "CRITICAL")
    level = db.scalar(
        select(Projection.risk_level).where(
            Projection.student_id == student_id(db, "S003"), Projection.subject_id.is_(None)
        )
    )
    assert level == "CRITICAL"


def test_att02_valid_xlsx_imported(admin, db):
    path = SAMPLE_CSV.with_suffix(".xlsx")
    r = upload(admin, path.read_bytes(), "attendance_sample.xlsx")
    assert r.status_code == 200, r.text
    assert r.json()["rows_processed"] == 24
    assert r.json()["file_type"] == "xlsx"


def test_att03_missing_column_rejected(admin, db):
    r = upload(admin, b"student_roll,subject_code,date,classes_conducted\nS001,CS101,2026-09-01,20\n")
    assert r.status_code == 422
    assert "Missing required column(s): classes_attended" in _messages(r)
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_att04_attended_greater_than_conducted_rejected_with_row_number(admin):
    r = upload(admin, (HEADER + "S001,CS101,2026-09-01,20,16\nS002,CS101,2026-09-01,10,12\n").encode())
    assert r.status_code == 422
    err = r.json()["errors"][0]
    assert err["row"] == 3 and err["column"] == "classes_attended"
    assert "cannot exceed conducted" in err["message"]
    assert r.json()["rows_rejected"] == 1


def test_att05_negative_value_rejected(admin):
    r = upload(admin, (HEADER + "S001,CS101,2026-09-01,10,-1\n").encode())
    assert r.status_code == 422
    assert "cannot be negative" in _messages(r)


def test_att06_duplicate_rows_in_file_rejected(admin):
    r = upload(admin, (HEADER + "S001,CS101,2026-09-01,10,8\nS001,CS101,2026-09-01,10,9\n").encode())
    assert r.status_code == 422
    assert "Duplicate record" in _messages(r) and "row 2" in _messages(r)


def test_att06_existing_records_strict_vs_replace(admin, db):
    assert upload(admin, sample_bytes()).status_code == 200
    again = upload(admin, sample_bytes())
    assert again.status_code == 422
    assert "already exists" in _messages(again)
    count = _count(db)
    replaced = upload(admin, sample_bytes(), mode="replace")
    assert replaced.status_code == 200
    assert replaced.json()["rows_updated"] == 24 and replaced.json()["rows_inserted"] == 0
    assert _count(db) == count


def test_att07_zero_conducted_rejected_without_crash(admin):
    r = upload(admin, (HEADER + "S001,CS101,2026-09-01,0,0\n").encode())
    assert r.status_code == 422
    assert "greater than 0" in _messages(r)


def test_att08_full_attendance_is_100_percent(admin, db):
    r = upload(admin, (HEADER + "S008,CS101,2026-09-01,20,20\n").encode())
    assert r.status_code == 200
    data = admin.get(f"/api/analytics/student/{student_id(db, 'S008')}").json()
    assert data["current_percentage"] == 100.0


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ("S001,CS101,2026-13-40,10,8", "Invalid date"),
        ("S001,CS101,01/09/2026,10,8", "Invalid date"),
        ("S001,CS101,2099-01-01,10,8", "future"),
        ("S001,CS101,2026-09-01,ten,8", "whole number"),
        ("S001,CS101,2026-09-01,10.5,8", "whole number"),
        ("S001,CS101,2026-09-01,,8", "required"),
        ("S999,CS101,2026-09-01,10,8", "Unknown student"),
        ("S001,XX999,2026-09-01,10,8", "Unknown subject"),
        ("S001,CS101,2026-09-01,5000,8", "unrealistically large"),
        ("S0'1;DROP,CS101,2026-09-01,10,8", "invalid characters"),
    ],
)
def test_row_validation(admin, row, expected):
    r = upload(admin, (HEADER + row + "\n").encode())
    assert r.status_code == 422
    assert expected in _messages(r)


def test_department_mismatch_rejected(admin):
    csv = (
        "student_roll,department,subject_code,date,classes_conducted,classes_attended\nS001,ECE,CS101,2026-09-01,10,8\n"
    )
    r = upload(admin, csv.encode())
    assert r.status_code == 422
    assert "registered in CSE" in _messages(r)


def test_one_bad_row_rejects_whole_file_atomically(admin, db):
    before = _count(db)
    imports_before = db.scalar(select(func.count(AttendanceImport.id)))
    content = sample_bytes() + b"S001,Aarav Sharma,CSE,2,CS101,Data Structures,2026-09-02,10,11\n"
    r = upload(admin, content)
    assert r.status_code == 422
    assert r.json()["rows_processed"] == 0 and r.json()["rows_rejected"] == 1
    assert _count(db) == before  # nothing persisted
    rejected = db.scalar(select(AttendanceImport).order_by(AttendanceImport.id.desc()))
    assert db.scalar(select(func.count(AttendanceImport.id))) == imports_before + 1
    assert rejected.status == "REJECTED"


def test_dry_run_validates_without_persisting(admin, db):
    before = _count(db)
    r = upload(admin, sample_bytes(), dry_run=True)
    assert r.status_code == 200
    assert r.json()["dry_run"] is True and r.json()["rows_processed"] == 24
    assert _count(db) == before


def test_invalid_example_file_reports_every_problem(admin):
    content = (SAMPLE_CSV.parent / "attendance_invalid_example.csv").read_bytes()
    r = upload(admin, content)
    assert r.status_code == 422
    body = r.json()
    assert body["rows_rejected"] >= 6
    rows = {e["row"] for e in body["errors"]}
    assert {2, 3, 4, 7, 9} <= rows


@pytest.mark.parametrize(
    ("filename", "content", "status"),
    [
        ("notes.txt", b"hello", 415),
        ("legacy.xls", b"\xd0\xcf\x11\xe0", 415),
        ("fake.xlsx", b"student_roll,subject_code\n", 415),
        ("zip-as.csv", b"PK\x03\x04rest", 415),
        ("empty.csv", b"", 422),
        ("headers-only.csv", HEADER.encode(), 422),
    ],
)
def test_file_level_rejections(admin, filename, content, status):
    r = upload(admin, content, filename)
    assert r.status_code == status, r.text
    assert r.json()["success"] is False
    assert r.json()["error"]["message"]


def test_oversized_upload_rejected(admin):
    settings = get_settings()
    original = settings.max_upload_mb
    settings.max_upload_mb = 0.001  # ~1 KB
    try:
        r = upload(admin, sample_bytes())
    finally:
        settings.max_upload_mb = original
    assert r.status_code == 413


def test_xlsx_with_header_aliases_and_blank_rows(admin):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Roll No", "Subject Code", "Date", "Conducted", "Attended"])
    ws.append(["s008", "cs102", "2026-09-01", 18, 18])
    ws.append([None, None, None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    r = upload(admin, buf.getvalue(), "aliases.xlsx")
    assert r.status_code == 200, r.text
    assert r.json()["rows_processed"] == 1


def test_register_new_students_and_subjects(admin, db):
    csv = (
        b"student_roll,student_name,department,semester,subject_code,subject_name,date,classes_conducted,classes_attended\n"
        b"S100,Test Learner,CSE,2,CS199,Compiler Design,2026-09-01,10,6\n"
    )
    assert upload(admin, csv).status_code == 422  # unknown by default
    r = upload(admin, csv, register_new=True)
    assert r.status_code == 200, r.text
    assert r.json()["created_students"] == ["S100"] and r.json()["created_subjects"] == ["CS199"]
    assert db.scalar(select(Student).where(Student.roll_number == "S100")).name == "Test Learner"
    assert db.scalar(select(Subject).where(Subject.code == "CS199")) is not None


def test_name_mismatch_is_warning_not_error(admin):
    csv = (
        "student_roll,student_name,subject_code,date,classes_conducted,classes_attended\n"
        "S001,A. Sharma,CS101,2026-09-01,10,8\n"
    )
    r = upload(admin, csv.encode())
    assert r.status_code == 200
    assert "differs from registered name" in r.json()["warnings"][0]["message"]


def test_import_history_visible_to_admin(admin):
    upload(admin, sample_bytes())
    items = admin.get("/api/attendance/imports").json()["items"]
    assert items[0]["status"] == "COMPLETED" and items[0]["rows_inserted"] == 24
