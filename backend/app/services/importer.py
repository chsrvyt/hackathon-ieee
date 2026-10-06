"""Attendance CSV/XLSX import.

Pipeline: read (size/type/structure checks) -> validate EVERY row -> if any error,
reject the whole file with a row-level report and change nothing -> otherwise persist
all rows and refresh analytics in one transaction.

Each row records the classes conducted and attended for one student in one subject
during the reporting period that ends on `date` (a single day or a longer period).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal

import pandas as pd
from sqlalchemy import insert, select, tuple_, update
from sqlalchemy.orm import Session

from ..analytics.service import refresh_projections
from ..config import get_settings
from ..models import AttendanceImport, AttendanceRecord, Department, Student, Subject, User, utcnow

REQUIRED_COLUMNS = ["student_roll", "subject_code", "date", "classes_conducted", "classes_attended"]
OPTIONAL_COLUMNS = ["student_name", "department", "semester", "subject_name"]
COLUMN_ALIASES = {
    "roll": "student_roll",
    "roll_no": "student_roll",
    "roll_number": "student_roll",
    "student_roll_number": "student_roll",
    "conducted": "classes_conducted",
    "attended": "classes_attended",
    "dept": "department",
    "department_code": "department",
    "sem": "semester",
}
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,31}$")
INT_RE = re.compile(r"^[+-]?\d+(\.0+)?$")
MAX_CLASSES_PER_ROW = 1000
MAX_REPORTED_ERRORS = 500
EARLIEST_DATE = date(2000, 1, 1)


@dataclass
class Issue:
    message: str
    row: int | None = None
    column: str | None = None
    value: str | None = None

    def to_dict(self) -> dict:
        return {"row": self.row, "column": self.column, "value": self.value, "message": self.message}


@dataclass
class ImportOptions:
    mode: Literal["strict", "replace"] = "strict"
    register_new: bool = False
    dry_run: bool = False


@dataclass
class ImportResult:
    success: bool
    filename: str
    file_type: str
    mode: str
    dry_run: bool = False
    import_id: int | None = None
    rows_total: int = 0
    rows_processed: int = 0
    rows_rejected: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    students_affected: int = 0
    subjects_affected: int = 0
    created_students: list[str] = field(default_factory=list)
    created_subjects: list[str] = field(default_factory=list)
    date_range: list[str] = field(default_factory=list)
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    risk_changes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "dry_run": self.dry_run,
            "import_id": self.import_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "mode": self.mode,
            "rows_total": self.rows_total,
            "rows_processed": self.rows_processed,
            "rows_rejected": self.rows_rejected,
            "rows_inserted": self.rows_inserted,
            "rows_updated": self.rows_updated,
            "students_affected": self.students_affected,
            "subjects_affected": self.subjects_affected,
            "created_students": self.created_students,
            "created_subjects": self.created_subjects,
            "date_range": self.date_range,
            "errors_total": len(self.errors),
            "errors": [e.to_dict() for e in self.errors[:MAX_REPORTED_ERRORS]],
            "warnings": [w.to_dict() for w in self.warnings[:MAX_REPORTED_ERRORS]],
            "risk_changes": self.risk_changes,
        }


class FileRejected(Exception):
    def __init__(self, issues: list[Issue], status_code: int = 422):
        super().__init__(issues[0].message if issues else "File rejected")
        self.issues = issues
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def detect_file_type(filename: str) -> str:
    name = (filename or "").lower().strip()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".xlsx"):
        return "xlsx"
    if name.endswith(".xls"):
        raise FileRejected([Issue("Legacy .xls files are not supported. Save the sheet as .xlsx or .csv.")], 415)
    raise FileRejected([Issue("Unsupported file type. Upload a .csv or .xlsx file.")], 415)


def _check_xlsx_container(data: bytes) -> None:
    settings = get_settings()
    if not data.startswith(b"PK\x03\x04"):
        raise FileRejected([Issue("The file has a .xlsx extension but is not a valid Excel workbook.")], 415)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            names = {i.filename for i in infos}
            total = sum(i.file_size for i in infos)
    except zipfile.BadZipFile as exc:
        raise FileRejected([Issue("The workbook is corrupted and could not be opened.")], 415) from exc
    if "xl/workbook.xml" not in names:
        raise FileRejected([Issue("The file is not a valid Excel workbook (.xlsx).")], 415)
    if len(infos) > 2000 or total > settings.max_xlsx_uncompressed_mb * 1024 * 1024:
        raise FileRejected([Issue("The workbook is too large to process safely.")], 413)


def _decode_csv(data: bytes) -> str:
    if data.startswith(b"PK\x03\x04"):
        raise FileRejected([Issue("This looks like an Excel workbook. Save it with a .xlsx extension.")], 415)
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 decodes almost everything
        raise FileRejected([Issue("The CSV file is not valid UTF-8 text.")], 415)
    if "\x00" in text:
        raise FileRejected([Issue("The CSV file contains binary data.")], 415)
    return text


def _normalise_header(name: object) -> str:
    key = re.sub(r"[\s\-]+", "_", str(name).strip().lower())
    return COLUMN_ALIASES.get(key, key)


def read_table(filename: str, data: bytes) -> tuple[str, pd.DataFrame]:
    settings = get_settings()
    file_type = detect_file_type(filename)
    if not data:
        raise FileRejected([Issue("The uploaded file is empty.")])
    if len(data) > settings.max_upload_bytes:
        raise FileRejected([Issue(f"The file exceeds the {settings.max_upload_mb:g} MB upload limit.")], 413)
    try:
        if file_type == "csv":
            frame = pd.read_csv(
                io.StringIO(_decode_csv(data)),
                dtype=str,
                keep_default_na=False,
                na_filter=False,
                skip_blank_lines=False,
                skipinitialspace=True,
            )
        else:
            _check_xlsx_container(data)
            frame = pd.read_excel(
                io.BytesIO(data), sheet_name=0, dtype=str, engine="openpyxl", keep_default_na=False, na_filter=False
            )
    except FileRejected:
        raise
    except pd.errors.EmptyDataError as exc:
        raise FileRejected([Issue("The file has no header row or data.")]) from exc
    except (pd.errors.ParserError, ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        message = "The file could not be parsed. Check that it is a well-formed CSV/XLSX table."
        raise FileRejected([Issue(message)]) from exc
    return file_type, frame


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _parse_int(raw: str) -> int | None:
    raw = raw.strip()
    if not INT_RE.match(raw):
        return None
    return int(float(raw)) if "." in raw else int(raw)


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[ T]00:00(?::00(?:\.0+)?)?)?$", raw)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


@dataclass
class ParsedRow:
    row: int
    roll: str
    subject_code: str
    date: date
    conducted: int
    attended: int
    student_name: str
    department: str
    semester: str
    subject_name: str


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def import_attendance(db: Session, user: User, filename: str, data: bytes, options: ImportOptions) -> ImportResult:
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", (filename or "upload")[-120:]) or "upload"
    result = ImportResult(False, safe_name, "", options.mode, dry_run=options.dry_run)
    try:
        result.file_type, frame = read_table(filename, data)
    except FileRejected as exc:
        result.errors = exc.issues
        raise

    # --- header checks ---------------------------------------------------------
    raw_headers = [str(c) for c in frame.columns]
    headers = [_normalise_header(c) for c in raw_headers]
    # pandas renames repeated headers to "name.1", "name.2"; map them back to detect duplicates.
    base_names = [re.sub(r"\.\d+$", "", h) if re.sub(r"\.\d+$", "", h) in headers else h for h in headers]
    dupes = sorted({h for h in base_names if base_names.count(h) > 1})
    if dupes:
        result.errors.append(Issue(f"Duplicate column(s): {', '.join(dupes)}."))
    frame.columns = headers
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        result.errors.append(
            Issue(
                f"Missing required column(s): {', '.join(missing)}. "
                f"Required columns are: {', '.join(REQUIRED_COLUMNS)}."
            )
        )
    if result.errors:
        return result
    unknown = [h for h in headers if h not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if unknown:
        result.warnings.append(Issue(f"Ignored unrecognised column(s): {', '.join(unknown)}."))
    for col in OPTIONAL_COLUMNS:
        if col not in frame.columns:
            frame[col] = ""

    frame = frame[REQUIRED_COLUMNS + OPTIONAL_COLUMNS].astype(str).apply(lambda s: s.str.strip())
    blank = (frame == "").all(axis=1)
    if blank.any():
        result.warnings.append(Issue(f"Skipped {int(blank.sum())} completely blank row(s)."))
    frame = frame[~blank]
    result.rows_total = len(frame)
    if result.rows_total == 0:
        result.errors.append(Issue("The file contains a header but no attendance rows."))
        return result
    settings = get_settings()
    if result.rows_total > settings.max_upload_rows:
        result.errors.append(Issue(f"Too many rows ({result.rows_total}). The limit is {settings.max_upload_rows}."))
        return result

    # --- per-row checks --------------------------------------------------------
    today = datetime.now(UTC).date() + timedelta(days=1)  # tolerate timezone skew
    bad_rows: set[int] = set()
    parsed: list[ParsedRow] = []
    seen: dict[tuple[str, str, date], int] = {}

    def err(row: int, column: str | None, value: str | None, message: str) -> None:
        bad_rows.add(row)
        result.errors.append(Issue(message, row, column, value))

    for idx, rec in zip(frame.index, frame.to_dict("records"), strict=True):
        row = int(idx) + 2  # spreadsheet row number (header is row 1)
        ok = True
        roll = rec["student_roll"].upper()
        code = rec["subject_code"].upper()
        for col, value in (("student_roll", roll), ("subject_code", code)):
            if not value:
                err(row, col, value, f"{col} is required.")
                ok = False
            elif not CODE_RE.match(value):
                err(row, col, value, f"{col} contains invalid characters.")
                ok = False
        d = _parse_date(rec["date"])
        if not rec["date"]:
            err(row, "date", "", "date is required.")
            ok = False
        elif d is None:
            err(row, "date", rec["date"], "Invalid date. Use the YYYY-MM-DD format, e.g. 2026-09-01.")
            ok = False
        elif d > today:
            err(row, "date", rec["date"], "Attendance date is in the future.")
            ok = False
        elif d < EARLIEST_DATE:
            err(row, "date", rec["date"], "Attendance date is implausibly old.")
            ok = False
        counts: dict[str, int] = {}
        for col in ("classes_conducted", "classes_attended"):
            raw = rec[col]
            value = _parse_int(raw) if raw else None
            if not raw:
                err(row, col, raw, f"{col} is required.")
                ok = False
            elif value is None:
                err(row, col, raw, f"{col} must be a whole number.")
                ok = False
            elif value < 0:
                err(row, col, raw, f"{col} cannot be negative.")
                ok = False
            elif value > MAX_CLASSES_PER_ROW:
                err(row, col, raw, f"{col} is unrealistically large (max {MAX_CLASSES_PER_ROW}).")
                ok = False
            else:
                counts[col] = value
        conducted, attended = counts.get("classes_conducted"), counts.get("classes_attended")
        if conducted is not None and conducted == 0:
            err(row, "classes_conducted", "0", "classes_conducted must be greater than 0.")
            ok = False
        if conducted is not None and attended is not None and attended > conducted:
            err(
                row,
                "classes_attended",
                rec["classes_attended"],
                f"Attendance cannot exceed conducted classes ({attended} attended > {conducted} conducted).",
            )
            ok = False
        if rec["semester"] and _parse_int(rec["semester"]) is None:
            err(row, "semester", rec["semester"], "semester must be a whole number.")
            ok = False
        if ok:
            key = (roll, code, d)
            if key in seen:
                err(row, None, None, f"Duplicate record: same student, subject and date as row {seen[key]}.")
                continue
            seen[key] = row
            parsed.append(
                ParsedRow(
                    row,
                    roll,
                    code,
                    d,
                    conducted,
                    attended,  # type: ignore[arg-type]
                    rec["student_name"],
                    rec["department"].upper(),
                    rec["semester"],
                    rec["subject_name"],
                )
            )

    # --- reference checks ------------------------------------------------------
    departments = {d.code: d for d in db.scalars(select(Department))}
    rolls = {p.roll for p in parsed}
    codes = {p.subject_code for p in parsed}
    students = {s.roll_number: s for s in db.scalars(select(Student).where(Student.roll_number.in_(rolls)))}
    subjects = {s.code: s for s in db.scalars(select(Subject).where(Subject.code.in_(codes)))}
    scope_dept = user.department_id if user.role == "ADMIN" else None
    new_students: dict[str, dict] = {}
    new_subjects: dict[str, dict] = {}
    warned_names: set[str] = set()

    for p in parsed:
        student = students.get(p.roll)
        if student is None:
            if not options.register_new:
                err(
                    p.row,
                    "student_roll",
                    p.roll,
                    f"Unknown student roll number '{p.roll}'. Register the student "
                    "first or enable 'Register new students and subjects'.",
                )
            else:
                dept = departments.get(p.department)
                sem = _parse_int(p.semester) if p.semester else None
                if not p.student_name or not p.department or sem is None:
                    err(p.row, "student_roll", p.roll, "New student requires student_name, department and semester.")
                elif dept is None:
                    err(p.row, "department", p.department, f"Unknown department '{p.department}'.")
                elif not 1 <= sem <= 12:
                    err(p.row, "semester", p.semester, "semester must be between 1 and 12.")
                elif scope_dept is not None and dept.id != scope_dept:
                    err(p.row, "department", p.department, "You can only import data for your own department.")
                else:
                    spec = {"name": p.student_name, "department": dept, "semester": sem}
                    prior = new_students.setdefault(p.roll, spec)
                    if prior["department"].id != dept.id or prior["name"] != p.student_name:
                        err(p.row, "student_roll", p.roll, "Conflicting name/department for the same new student.")
        else:
            if p.department and student.department.code != p.department:
                err(
                    p.row,
                    "department",
                    p.department,
                    f"Student {p.roll} is registered in {student.department.code}, not {p.department}.",
                )
            if scope_dept is not None and student.department_id != scope_dept:
                err(p.row, "student_roll", p.roll, "This student is outside your department scope.")
            if p.student_name and p.student_name.lower() != student.name.lower() and p.roll not in warned_names:
                warned_names.add(p.roll)
                result.warnings.append(
                    Issue(
                        f"Name '{p.student_name}' differs from registered name '{student.name}'.",
                        p.row,
                        "student_name",
                        p.student_name,
                    )
                )

        subject = subjects.get(p.subject_code)
        if subject is None:
            if not options.register_new:
                err(p.row, "subject_code", p.subject_code, f"Unknown subject code '{p.subject_code}'.")
            else:
                dept = departments.get(p.department) or (student.department if student else None)
                if not p.subject_name or dept is None:
                    err(p.row, "subject_code", p.subject_code, "New subject requires subject_name and department.")
                else:
                    spec = {"name": p.subject_name, "department": dept}
                    prior = new_subjects.setdefault(p.subject_code, spec)
                    if prior["name"] != p.subject_name or prior["department"].id != dept.id:
                        err(
                            p.row,
                            "subject_code",
                            p.subject_code,
                            "Conflicting name/department for the same new subject.",
                        )

    if result.errors:
        result.rows_rejected = len(bad_rows)
        _sort_issues(result)
        return result

    # --- conflicts with existing records -----------------------------------------
    existing: dict[tuple[int, int, date], int] = {}
    known_pairs = [
        (students[p.roll].id, subjects[p.subject_code].id, p.date)
        for p in parsed
        if p.roll in students and p.subject_code in subjects
    ]
    for start in range(0, len(known_pairs), 1000):
        chunk = known_pairs[start : start + 1000]
        rows = db.execute(
            select(
                AttendanceRecord.id, AttendanceRecord.student_id, AttendanceRecord.subject_id, AttendanceRecord.date
            ).where(tuple_(AttendanceRecord.student_id, AttendanceRecord.subject_id, AttendanceRecord.date).in_(chunk))
        )
        for rid, sid, subid, d in rows:
            existing[(sid, subid, d)] = rid
    if existing and options.mode == "strict":
        for p in parsed:
            if p.roll in students and p.subject_code in subjects:
                if (students[p.roll].id, subjects[p.subject_code].id, p.date) in existing:
                    err(
                        p.row,
                        None,
                        None,
                        f"A record for {p.roll} / {p.subject_code} on {p.date.isoformat()} already exists. "
                        "Choose 'Replace existing records' to overwrite it.",
                    )
        result.rows_rejected = len(bad_rows)
        _sort_issues(result)
        return result

    # --- summary (also returned for dry runs) --------------------------------------
    result.rows_processed = len(parsed)
    result.students_affected = len(rolls)
    result.subjects_affected = len(codes)
    dates = sorted({p.date for p in parsed})
    result.date_range = [dates[0].isoformat(), dates[-1].isoformat()]
    result.created_students = sorted(new_students)
    result.created_subjects = sorted(new_subjects)
    result.rows_updated = len(existing)
    result.rows_inserted = len(parsed) - len(existing)
    _sort_issues(result)
    if options.dry_run:
        result.success = True
        return result

    # --- persist (single transaction, committed by caller) ------------------------------
    for roll, spec in new_students.items():
        s = Student(roll_number=roll, name=spec["name"], department_id=spec["department"].id, semester=spec["semester"])
        db.add(s)
        students[roll] = s
    for code, spec in new_subjects.items():
        s = Subject(code=code, name=spec["name"], department_id=spec["department"].id)
        db.add(s)
        subjects[code] = s
    imp = AttendanceImport(
        uploaded_by=user.id,
        filename=safe_name,
        file_type=result.file_type,
        mode=options.mode,
        status="COMPLETED",
        rows_total=result.rows_total,
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
    )
    db.add(imp)
    db.flush()

    inserts, updates = [], []
    now = utcnow()
    for p in parsed:
        sid, subid = students[p.roll].id, subjects[p.subject_code].id
        rid = existing.get((sid, subid, p.date))
        values = {"classes_conducted": p.conducted, "classes_attended": p.attended, "import_id": imp.id}
        if rid is None:
            inserts.append(
                {"student_id": sid, "subject_id": subid, "date": p.date, "created_at": now, "updated_at": now, **values}
            )
        else:
            updates.append({"id": rid, "updated_at": now, **values})
    if inserts:
        db.execute(insert(AttendanceRecord), inserts)
    if updates:
        db.execute(update(AttendanceRecord), updates)

    changes = refresh_projections(db, [students[r].id for r in rolls])
    result.risk_changes = [c.to_dict() for c in changes]
    result.import_id = imp.id
    result.success = True
    return result


def _sort_issues(result: ImportResult) -> None:
    result.errors.sort(key=lambda i: i.row or 0)
    result.warnings.sort(key=lambda i: i.row or 0)


def record_rejected_import(db: Session, user: User, result: ImportResult) -> None:
    db.add(
        AttendanceImport(
            uploaded_by=user.id,
            filename=result.filename,
            file_type=result.file_type or "unknown",
            mode=result.mode,
            status="REJECTED",
            rows_total=result.rows_total,
            rows_rejected=result.rows_rejected,
        )
    )
    db.commit()


TEMPLATE_CSV = (
    "student_roll,student_name,department,semester,subject_code,subject_name,date,classes_conducted,classes_attended\n"
    "S001,Aarav Sharma,CSE,2,CS101,Data Structures,2026-09-01,20,16\n"
)
