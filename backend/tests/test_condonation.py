"""Condonation workflow: submit -> PENDING -> APPROVED/REJECTED, with permission and transition checks."""

from sqlalchemy import select

from app.models import Subject

from .conftest import make_client, student_id

REASON = "I was unwell with typhoid for ten days in August and have a medical certificate."


def _submit(client, **extra):
    return client.post("/api/condonation", json={"reason": REASON, **extra})


def test_full_workflow_submit_review_and_student_sees_decision(student, mentor, db):
    r = _submit(student)
    assert r.status_code == 201, r.text
    req = r.json()["request"]
    assert req["status"] == "PENDING" and req["attendance_at_request"] is not None

    pending = mentor.get("/api/condonation/pending").json()
    assert pending["can_review"] is True
    assert req["id"] in [p["id"] for p in pending["items"]]
    assert any(a["kind"] == "CONDONATION" for a in mentor.get("/api/alerts").json()["items"])

    d = mentor.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "APPROVED", "comment": "Verified."})
    assert d.status_code == 200
    assert d.json()["request"]["status"] == "APPROVED"
    assert d.json()["request"]["reviewed_by"]["name"] == "Prof. Kavita Rao"

    mine = student.get(f"/api/condonation/student/{student_id(db, 'S003')}").json()["items"]
    assert mine[0]["status"] == "APPROVED" and mine[0]["review_comment"] == "Verified."
    assert [h["to_status"] for h in mine[0]["history"]] == ["PENDING", "APPROVED"]
    alerts = student.get("/api/alerts").json()["items"]
    assert any("approved" in a["message"] for a in alerts)


def test_reject_requires_comment_and_is_final(student, admin):
    req = _submit(student).json()["request"]
    r = admin.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "REJECTED"})
    assert r.status_code == 422
    r = admin.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "REJECTED", "comment": "No proof."})
    assert r.status_code == 200 and r.json()["request"]["status"] == "REJECTED"
    again = admin.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "APPROVED"})
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_TRANSITION"


def test_student_cannot_approve_own_request(student):
    req = _submit(student).json()["request"]
    r = student.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "APPROVED"})
    assert r.status_code == 403


def test_unrelated_reviewers_cannot_decide(student, mentor_ece, hod_ece, exam_cell):
    req = _submit(student).json()["request"]
    for client in (mentor_ece, hod_ece, exam_cell):
        r = client.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "APPROVED"})
        assert r.status_code == 403
    assert req["id"] not in [p["id"] for p in mentor_ece.get("/api/condonation/pending").json()["items"]]


def test_duplicate_pending_request_rejected(student):
    assert _submit(student).status_code == 201
    r = _submit(student)
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_PENDING"


def test_subject_specific_request(student, db):
    os_id = db.scalar(select(Subject.id).where(Subject.code == "CS103"))
    r = _submit(student, subject_id=os_id)
    assert r.status_code == 201
    assert r.json()["request"]["subject"]["code"] == "CS103"


def test_ineligible_student_cannot_submit(db):
    isha = make_client("s008@attendai.demo")  # 100 % attendance
    r = _submit(isha)
    assert r.status_code == 422 and r.json()["error"]["code"] == "NOT_ELIGIBLE"


def test_staff_cannot_submit_and_reason_is_validated(mentor, student):
    assert _submit(mentor).status_code == 403
    r = student.post("/api/condonation", json={"reason": "short"})
    assert r.status_code == 422


def test_withdraw_rules(student, mentor):
    req = _submit(student).json()["request"]
    other = make_client("s005@attendai.demo")
    assert other.patch(f"/api/condonation/{req['id']}/withdraw").status_code == 403
    w = student.patch(f"/api/condonation/{req['id']}/withdraw")
    assert w.status_code == 200 and w.json()["request"]["status"] == "WITHDRAWN"
    late = mentor.patch(f"/api/condonation/{req['id']}/decision", json={"decision": "APPROVED"})
    assert late.status_code == 409


def test_unknown_request_is_404(admin):
    assert admin.patch("/api/condonation/99999/decision", json={"decision": "APPROVED"}).status_code == 404


def test_seeded_requests_visible_by_scope(exam_cell, mentor):
    statuses = {r["status"] for r in exam_cell.get("/api/condonation").json()["items"]}
    assert statuses == {"PENDING", "APPROVED"}
    mine = mentor.get("/api/condonation").json()["items"]
    assert all(r["student"]["department"] == "CSE" for r in mine)
