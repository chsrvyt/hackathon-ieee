"""Server-side authorization (IDOR/BOLA) for every role. The UI is never trusted."""

import pytest

from .conftest import student_id, upload


@pytest.mark.parametrize(
    "path",
    [
        "/api/students/{id}",
        "/api/analytics/student/{id}",
        "/api/attendance/student/{id}",
        "/api/condonation/student/{id}",
    ],
)
def test_student_cannot_read_another_student(student, db, path):
    other = student_id(db, "S001")
    r = student.get(path.format(id=other))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    own = student_id(db, "S003")
    assert student.get(path.format(id=own)).status_code == 200


def test_student_cannot_use_staff_endpoints(student, db):
    for path in (
        "/api/students",
        "/api/analytics/overview",
        "/api/analytics/risk-students",
        "/api/condonation/pending",
        "/api/attendance/imports",
        "/api/analytics/department/1",
        "/api/reports/department/1/export.csv",
        f"/api/attendance/subject/{1}",
    ):
        assert student.get(path).status_code == 403, path
    assert upload(student, b"x").status_code == 403
    assert student.post("/api/analytics/recompute").status_code == 403


def test_unknown_student_is_404_not_500(admin):
    assert admin.get("/api/students/999999").status_code == 404


def test_mentor_sees_only_assigned_students(mentor, db):
    items = mentor.get("/api/students?page_size=100").json()["items"]
    assert {s["roll_number"] for s in items} == {f"S00{i}" for i in range(1, 9)}
    assert mentor.get(f"/api/analytics/student/{student_id(db, 'S003')}").status_code == 200
    assert mentor.get(f"/api/analytics/student/{student_id(db, 'E001')}").status_code == 403
    risk = mentor.get("/api/analytics/risk-students").json()["items"]
    assert risk and all(r["department"] == "CSE" for r in risk)


def test_mentor_cannot_upload_or_view_department_report(mentor):
    assert upload(mentor, b"x").status_code == 403
    assert mentor.get("/api/analytics/department/1").status_code == 403


def test_hod_is_limited_to_own_department(hod_ece, db):
    items = hod_ece.get("/api/students?page_size=100").json()["items"]
    assert items and all(s["department"]["code"] == "ECE" for s in items)
    assert hod_ece.get(f"/api/students/{student_id(db, 'S003')}").status_code == 403
    deps = {d["code"]: d["id"] for d in hod_ece.get("/api/departments").json()["items"]}
    assert set(deps) == {"ECE"}
    from sqlalchemy import select

    from app.models import Department

    cse = db.scalar(select(Department.id).where(Department.code == "CSE"))
    assert hod_ece.get(f"/api/analytics/department/{cse}").status_code == 403
    assert hod_ece.get(f"/api/analytics/department/{deps['ECE']}").status_code == 200


def test_hod_cannot_import_other_department_rows(hod_ece):
    csv = b"student_roll,subject_code,date,classes_conducted,classes_attended\nS001,CS101,2026-09-01,20,16\n"
    r = upload(hod_ece, csv)
    assert r.status_code == 422
    assert "outside your department scope" in r.json()["errors"][0]["message"]


def test_exam_cell_is_read_only(exam_cell, db):
    assert exam_cell.get("/api/analytics/overview").json()["total_students"] == 14
    assert exam_cell.get(f"/api/analytics/student/{student_id(db, 'E002')}").status_code == 200
    assert upload(exam_cell, b"x").status_code == 403
    assert exam_cell.post("/api/analytics/recompute").status_code == 403
    pending = exam_cell.get("/api/condonation/pending").json()
    assert pending["can_review"] is False
    req_id = pending["items"][0]["id"]
    r = exam_cell.patch(f"/api/condonation/{req_id}/decision", json={"decision": "APPROVED"})
    assert r.status_code == 403


def test_admin_has_institution_scope(admin):
    overview = admin.get("/api/analytics/overview").json()
    assert overview["total_students"] == 14
    assert {d["department"]["code"] for d in overview["departments"]} == {"CSE", "ECE"}


def test_alerts_are_private_to_recipient(student, mentor):
    mentor_alerts = mentor.get("/api/alerts").json()["items"]
    assert mentor_alerts
    r = student.patch(f"/api/alerts/{mentor_alerts[0]['id']}/read")
    assert r.status_code == 404
    own = student.get("/api/alerts").json()
    assert all(a["student_id"] == own["items"][0]["student_id"] for a in own["items"])


def test_student_scope_filters_cannot_be_widened_by_query(mentor, db):
    # A department filter for a department the mentor has no students in yields nothing, not foreign data.
    from sqlalchemy import select

    from app.models import Department

    ece = db.scalar(select(Department.id).where(Department.code == "ECE"))
    assert mentor.get(f"/api/students?department_id={ece}").json()["total"] == 0
