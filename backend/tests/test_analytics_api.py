"""Analytics, reporting, recovery calculator and platform endpoints over HTTP."""

import csv
import io

from sqlalchemy import select

from app.models import Department

from .conftest import sample_bytes, student_id, upload

EXPLAIN_KEYS = (
    "current_percentage",
    "target_percentage",
    "trend",
    "projected_percentage",
    "risk_level",
    "reason",
    "recommended_action",
    "recovery",
)


def test_student_analytics_is_fully_explained(student, db):
    data = student.get(f"/api/analytics/student/{student_id(db, 'S003')}").json()
    for key in EXPLAIN_KEYS:
        assert data[key] is not None, key
    assert data["target_percentage"] == 75.0
    assert data["projection"]["remaining_classes"] if "projection" in data else data["overall"]["projection"]
    assert len(data["subjects"]) == 3
    assert data["timeline"][-1]["cumulative_percentage"] == data["current_percentage"]
    assert "not a guarantee" in data["disclaimer"]


def test_demo_story_after_sample_upload(admin, db):
    upload(admin, sample_bytes())
    data = admin.get(f"/api/analytics/student/{student_id(db, 'S003')}").json()
    assert data["risk_level"] == "CRITICAL"
    assert data["trend"] == "DECREASING"
    assert data["current_percentage"] < 75 and data["projected_percentage"] < 75
    assert data["recovery"]["possible"] is True and data["recovery"]["classes_required"] > 0
    a, c, x = (
        data["overall"]["classes_attended"],
        data["overall"]["classes_conducted"],
        data["recovery"]["classes_required"],
    )
    assert (a + x) / (c + x) >= 0.75 > (a + x - 1) / (c + x - 1)


def test_unrecoverable_subject_recommends_condonation(admin, db):
    upload(admin, sample_bytes())
    data = admin.get(f"/api/analytics/student/{student_id(db, 'S005')}").json()
    os_subject = next(s for s in data["subjects"] if s["subject"]["code"] == "CS103")
    assert os_subject["risk_level"] == "CRITICAL"
    assert os_subject["recovery"]["possible"] is False
    assert "condonation" in os_subject["recommended_action"]


def test_recovery_calculator_endpoint(student):
    r = student.get("/api/analytics/recovery?attended=72&conducted=100&target=75&remaining=40").json()
    assert r["classes_required"] == 12 and r["status"] == "RECOVERABLE" and r["current_percentage"] == 72.0
    assert student.get("/api/analytics/recovery?attended=99&conducted=100&target=100").json()["status"] == "UNREACHABLE"
    assert student.get("/api/analytics/recovery?attended=0&conducted=0").json()["status"] == "NO_DATA"
    bad = student.get("/api/analytics/recovery?attended=11&conducted=10")
    assert bad.status_code == 422


def test_overview_totals_are_consistent(admin):
    o = admin.get("/api/analytics/overview").json()
    assert o["total_students"] == 14
    assert sum(o["risk_distribution"].values()) == 14
    assert sum(b["count"] for b in o["attendance_histogram"]) == o["students_with_data"]
    assert sum(d["students"] for d in o["departments"]) == 14
    assert o["at_risk_total"] == o["risk_distribution"]["CRITICAL"] + o["risk_distribution"]["WARNING"]
    assert len(o["subjects"]) == 6
    assert o["pending_condonations"] == 1
    assert o["recent_imports"]


def test_mentor_overview_scoped(mentor):
    o = mentor.get("/api/analytics/overview").json()
    assert o["total_students"] == 8 and o["scope"]["label"] == "My assigned students"


def test_students_list_filters_and_pagination(admin):
    r = admin.get("/api/students?risk=CRITICAL&page_size=2").json()
    assert r["total"] >= 1 and len(r["items"]) <= 2
    assert all(s["analytics"]["risk_level"] == "CRITICAL" for s in r["items"])
    found = admin.get("/api/students?search=rohan").json()["items"]
    assert [s["roll_number"] for s in found] == ["S003"]
    assert admin.get("/api/students?search=%25").json()["total"] == 0  # LIKE wildcards are escaped
    assert admin.get("/api/students?risk=BOGUS").status_code == 422


def test_department_report_and_csv_export(admin, exam_cell, db):
    upload(admin, sample_bytes())
    cse = db.scalar(select(Department.id).where(Department.code == "CSE"))
    report = exam_cell.get(f"/api/analytics/department/{cse}").json()
    assert report["department"]["code"] == "CSE" and report["total_students"] == 8
    assert report["shortage_count"] == sum(1 for s in report["shortage_students"] if s["overall_below_target"])
    rolls = {s["roll_number"] for s in report["shortage_students"]}
    assert {"S003", "S005"} <= rolls and "S008" not in rolls

    r = exam_cell.get(f"/api/reports/department/{cse}/export.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[2][0] == "roll_number"
    assert {row[0] for row in rows[3:]} == rolls


def test_csv_export_neutralises_formula_injection():
    from app.services.reports import _safe_cell

    assert _safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert _safe_cell("+1") == "'+1" and _safe_cell("ok") == "ok" and _safe_cell(5) == 5


def test_recompute_is_idempotent(admin):
    r = admin.post("/api/analytics/recompute").json()
    assert r["students_recomputed"] == 14 and r["risk_changes"] == []


def test_alerts_mark_read(student):
    alerts = student.get("/api/alerts").json()
    assert alerts["unread_count"] >= 1
    first = alerts["items"][0]["id"]
    assert student.patch(f"/api/alerts/{first}/read").json()["alert"]["is_read"] is True
    assert student.post("/api/alerts/read-all").status_code == 200
    assert student.get("/api/alerts").json()["unread_count"] == 0


def test_health_and_error_contract(anon):
    assert anon.get("/health").json() == {"status": "ok"}
    r = anon.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    h = anon.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"


def test_request_id_is_sanitised(anon):
    assert anon.get("/health", headers={"X-Request-ID": "abc-123"}).headers["x-request-id"] == "abc-123"
    echoed = anon.get("/health", headers={"X-Request-ID": "bad id;<script>"}).headers["x-request-id"]
    assert echoed != "bad id;<script>" and echoed.isalnum()


def test_subject_attendance_scoped(mentor, mentor_ece, db):
    from app.models import Subject

    cs101 = db.scalar(select(Subject.id).where(Subject.code == "CS101"))
    assert len(mentor.get(f"/api/attendance/subject/{cs101}").json()["students"]) == 8
    assert mentor_ece.get(f"/api/attendance/subject/{cs101}").json()["students"] == []


def test_version_reports_deployed_commit_without_auth(anon, monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert anon.get("/api/version").json() == {"commit": None}
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert anon.get("/api/version").json() == {"commit": "abc123"}
