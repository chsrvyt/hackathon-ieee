"""Demo data seeding (fictional people only).

Creates departments, subjects, demo accounts and the student roster, then loads the
attendance *history* through the real import pipeline (validation -> persistence ->
analytics -> alerts), exactly like an uploaded file. The newest CSE period
(2026-09-01, sample_data/attendance_sample.csv) is deliberately NOT seeded: the demo
uploads it to show the risk picture change.

Usage:
    python -m app.seed            # seed if the database has no demo admin yet (idempotent)
    python -m app.seed --reset    # wipe ALL application data and reseed
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import Department, Student, Subject, User
from .security import hash_password
from .services.condonation import decide_request, submit_request
from .services.importer import ImportOptions, import_attendance

log = logging.getLogger("attendai.seed")

DEPARTMENTS = [("CSE", "Computer Science & Engineering"), ("ECE", "Electronics & Communication Engineering")]

SUBJECTS = [
    # code, name, department, planned classes this semester, classes per seeded period
    ("CS101", "Data Structures", "CSE", 80, 10),
    ("CS102", "DBMS", "CSE", 72, 9),
    ("CS103", "Operating Systems", "CSE", 80, 10),
    ("EC101", "Signals & Systems", "ECE", 72, 9),
    ("EC102", "Digital Electronics", "ECE", 72, 9),
    ("EC103", "Network Theory", "ECE", 64, 8),
]

DEMO_ACCOUNTS = [
    {
        "email": "admin@attendai.demo",
        "name": "Dr. Neha Kapoor",
        "role": "ADMIN",
        "dept": None,
        "label": "Admin (all departments)",
    },
    {
        "email": "hod.ece@attendai.demo",
        "name": "Dr. Suresh Menon",
        "role": "ADMIN",
        "dept": "ECE",
        "label": "HOD, ECE (department scope)",
    },
    {
        "email": "mentor@attendai.demo",
        "name": "Prof. Kavita Rao",
        "role": "MENTOR",
        "dept": "CSE",
        "label": "Mentor (CSE students)",
    },
    {
        "email": "mentor.ece@attendai.demo",
        "name": "Prof. Arjun Nair",
        "role": "MENTOR",
        "dept": "ECE",
        "label": "Mentor (ECE students)",
    },
    {
        "email": "examcell@attendai.demo",
        "name": "Examination Cell",
        "role": "EXAM_CELL",
        "dept": None,
        "label": "Exam Cell (read-only reporting)",
    },
    {
        "email": "student@attendai.demo",
        "name": "Rohan Verma",
        "role": "STUDENT",
        "dept": "CSE",
        "label": "Student – Rohan Verma (S003)",
    },
]

# roll, name, department, semester, mentor email, login email
STUDENTS = [
    ("S001", "Aarav Sharma", "CSE", 2, "mentor@attendai.demo", "s001@attendai.demo"),
    ("S002", "Diya Patil", "CSE", 2, "mentor@attendai.demo", "s002@attendai.demo"),
    ("S003", "Rohan Verma", "CSE", 2, "mentor@attendai.demo", "student@attendai.demo"),
    ("S004", "Meera Joshi", "CSE", 2, "mentor@attendai.demo", "s004@attendai.demo"),
    ("S005", "Kabir Singh", "CSE", 2, "mentor@attendai.demo", "s005@attendai.demo"),
    ("S006", "Ananya Kulkarni", "CSE", 2, "mentor@attendai.demo", "s006@attendai.demo"),
    ("S007", "Vihaan Shah", "CSE", 2, "mentor@attendai.demo", "s007@attendai.demo"),
    ("S008", "Isha Deshmukh", "CSE", 2, "mentor@attendai.demo", "s008@attendai.demo"),
    ("E001", "Sneha Iyer", "ECE", 3, "mentor.ece@attendai.demo", "e001@attendai.demo"),
    ("E002", "Karthik Reddy", "ECE", 3, "mentor.ece@attendai.demo", "e002@attendai.demo"),
    ("E003", "Pooja Desai", "ECE", 3, "mentor.ece@attendai.demo", "e003@attendai.demo"),
    ("E004", "Aditya Rao", "ECE", 3, "mentor.ece@attendai.demo", "e004@attendai.demo"),
    ("E005", "Nisha Gupta", "ECE", 3, "mentor.ece@attendai.demo", "e005@attendai.demo"),
    ("E006", "Farhan Khan", "ECE", 3, "mentor.ece@attendai.demo", "e006@attendai.demo"),
]

CSE_PERIODS = [date(2026, 7, 20), date(2026, 8, 3), date(2026, 8, 17)]
ECE_PERIODS = [date(2026, 7, 20), date(2026, 8, 3), date(2026, 8, 17), date(2026, 9, 1)]

# Attendance rate per subject per seeded period (fictional, chosen to give a realistic mix).
PROFILES: dict[str, dict[str, list[float]]] = {
    "S001": {"CS101": [0.9, 0.9, 0.8], "CS102": [0.89, 0.89, 0.78], "CS103": [0.9, 0.9, 0.8]},
    "S002": {"CS101": [1, 0.9, 1], "CS102": [1, 0.89, 1], "CS103": [0.9, 1, 0.9]},
    "S003": {"CS101": [0.8, 0.8, 0.8], "CS102": [0.89, 0.78, 0.78], "CS103": [0.8, 0.8, 0.7]},
    "S004": {"CS101": [0.6, 0.7, 0.8], "CS102": [0.67, 0.67, 0.78], "CS103": [0.7, 0.7, 0.8]},
    "S005": {"CS101": [0.6, 0.5, 0.5], "CS102": [0.67, 0.56, 0.56], "CS103": [0.5, 0.4, 0.4]},
    "S006": {"CS101": [0.9, 0.9, 0.9], "CS102": [0.89, 0.89, 0.89], "CS103": [0.9, 0.8, 0.9]},
    "S007": {"CS101": [0.9, 0.8, 0.8], "CS102": [0.89, 0.78, 0.78], "CS103": [0.8, 0.8, 0.7]},
    "S008": {"CS101": [1, 1, 1], "CS102": [1, 1, 1], "CS103": [1, 1, 1]},
    "E001": {c: [0.9, 0.9, 1, 0.9] for c in ("EC101", "EC102", "EC103")},
    "E002": {"EC101": [0.67, 0.56, 0.56, 0.44], "EC102": [0.78, 0.67, 0.56, 0.56], "EC103": [0.75, 0.63, 0.5, 0.5]},
    "E003": {"EC101": [1, 0.89, 0.78, 0.67], "EC102": [0.89, 0.89, 0.78, 0.67], "EC103": [1, 0.88, 0.75, 0.75]},
    "E004": {c: [0.89, 0.78, 0.89, 0.89] for c in ("EC101", "EC102", "EC103")},
    "E005": {c: [1, 1, 0.89, 1] for c in ("EC101", "EC102", "EC103")},
    "E006": {"EC101": [0.56, 0.67, 0.78, 0.89], "EC102": [0.67, 0.67, 0.78, 0.89], "EC103": [0.5, 0.63, 0.75, 1]},
}

HEADER = (
    "student_roll,student_name,department,semester,subject_code,subject_name,date,classes_conducted,classes_attended"
)


def history_csv() -> str:
    subjects = {code: (name, dept, per_period) for code, name, dept, _planned, per_period in SUBJECTS}
    students = {roll: (name, dept, sem) for roll, name, dept, sem, _m, _e in STUDENTS}
    lines = [HEADER]
    for roll, subjects_rates in PROFILES.items():
        name, dept, sem = students[roll]
        periods = CSE_PERIODS if dept == "CSE" else ECE_PERIODS
        for code, rates in subjects_rates.items():
            subject_name, _sdept, conducted = subjects[code]
            for d, rate in zip(periods, rates, strict=True):
                attended = min(conducted, round(rate * conducted))
                lines.append(f"{roll},{name},{dept},{sem},{code},{subject_name},{d.isoformat()},{conducted},{attended}")
    return "\n".join(lines) + "\n"


def _wipe(db: Session) -> None:
    db.execute(
        text(
            "TRUNCATE alerts, condonation_events, condonation_requests, projections, attendance_records, "
            "attendance_imports, sessions, students, subjects, users, departments RESTART IDENTITY CASCADE"
        )
    )
    db.commit()


def seed(db: Session, reset: bool = False) -> bool:
    settings = get_settings()
    if reset:
        _wipe(db)
    if db.scalar(select(User.id).where(User.email == "admin@attendai.demo")):
        log.info("Demo data already present; skipping seed.")
        return False

    password_hash = hash_password(settings.demo_password)
    depts = {}
    for code, name in DEPARTMENTS:
        depts[code] = Department(code=code, name=name)
        db.add(depts[code])
    db.flush()
    for code, name, dept, planned, _ in SUBJECTS:
        db.add(Subject(code=code, name=name, department_id=depts[dept].id, planned_classes=planned))
    users = {}
    for acc in DEMO_ACCOUNTS:
        users[acc["email"]] = User(
            name=acc["name"],
            email=acc["email"],
            role=acc["role"],
            password_hash=password_hash,
            department_id=depts[acc["dept"]].id if acc["dept"] else None,
        )
        db.add(users[acc["email"]])
    for _roll, name, dept, _sem, _mentor, email in STUDENTS:
        if email not in users:
            users[email] = User(
                name=name, email=email, role="STUDENT", password_hash=password_hash, department_id=depts[dept].id
            )
            db.add(users[email])
    db.flush()
    for roll, name, dept, sem, mentor, email in STUDENTS:
        db.add(
            Student(
                roll_number=roll,
                name=name,
                department_id=depts[dept].id,
                semester=sem,
                mentor_id=users[mentor].id,
                user_id=users[email].id,
            )
        )
    db.flush()

    admin = users["admin@attendai.demo"]
    result = import_attendance(db, admin, "seed_history.csv", history_csv().encode(), ImportOptions())
    if not result.success:
        db.rollback()
        raise RuntimeError(f"Seed history import failed: {[e.message for e in result.errors[:5]]}")
    db.commit()

    # Condonation examples created through the same service functions the API uses.
    kabir = users["s005@attendai.demo"]
    os_subject = db.scalar(select(Subject).where(Subject.code == "CS103"))
    db.refresh(kabir)
    submit_request(
        db,
        kabir,
        "I was hospitalised for dengue from 3 to 14 August and have a discharge summary from the hospital.",
        os_subject.id,
    )
    db.commit()
    karthik = users["e002@attendai.demo"]
    db.refresh(karthik)
    req, _ = submit_request(
        db,
        karthik,
        "I represented the college at the inter-university athletics meet for two weeks in August.",
        None,
    )
    db.commit()
    decide_request(
        db,
        users["mentor.ece@attendai.demo"],
        req.id,
        "APPROVED",
        "Verified with the sports department; participation certificate on file.",
    )
    db.commit()
    log.info("Seeded demo data: %s students, %s history rows.", len(STUDENTS), result.rows_processed)
    return True


def main() -> int:
    logging.basicConfig(level="INFO", format="%(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Seed AttendAI demo data")
    parser.add_argument("--reset", action="store_true", help="wipe all application data first")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        seed(db, reset=args.reset)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
