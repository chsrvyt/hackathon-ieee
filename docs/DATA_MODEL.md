# AttendAI — Data Model (as implemented)

PostgreSQL 16. Models: `backend/app/models.py`. Migration: `backend/alembic/versions/0001_initial_schema.py`
(verified to upgrade, downgrade and re-upgrade cleanly, and `alembic check` reports no drift).

## Tables

| Table | Key columns | Integrity |
|---|---|---|
| `departments` | `code` (e.g. CSE), `name` | `code` UNIQUE, `name` UNIQUE |
| `users` | `name`, `email`, `password_hash` (scrypt), `role`, `department_id` (HOD scope for ADMIN; NULL = institution), `is_active`, timestamps | `email` UNIQUE (stored lower-case); CHECK `role IN (STUDENT, MENTOR, ADMIN, EXAM_CELL)`; FK department ON DELETE SET NULL |
| `sessions` | `user_id`, `token_hash` (HMAC-SHA256), `expires_at`, `revoked_at` | `token_hash` UNIQUE; FK user CASCADE |
| `students` | `roll_number`, `name`, `department_id`, `semester`, `mentor_id` → users, `user_id` → users (login) | `roll_number` UNIQUE, `user_id` UNIQUE; CHECK semester 1–12; department RESTRICT; mentor/user SET NULL |
| `subjects` | `code`, `name`, `department_id`, `planned_classes` | `code` UNIQUE; CHECK planned_classes > 0 |
| `attendance_imports` | uploader, filename (sanitised), type, mode, status, row counts | CHECK status IN (COMPLETED, REJECTED) |
| `attendance_records` | `student_id`, `subject_id`, `date`, `classes_conducted`, `classes_attended`, `import_id` | **UNIQUE (student_id, subject_id, date)**; CHECK conducted ≥ 0, attended ≥ 0, **attended ≤ conducted**; student CASCADE, subject RESTRICT |
| `projections` | latest analytics per student (`subject_id` NULL = overall) and per subject: attended, conducted, current/projected/target %, trend, risk_level, reason, recommended_action, classes_required, recovery_possible, calculated_at | partial UNIQUE (student) WHERE subject IS NULL; partial UNIQUE (student, subject) WHERE subject IS NOT NULL; CHECK risk/trend values |
| `alerts` | `recipient_user_id`, `student_id`, kind, severity, message, `is_read`, `read_at` | CHECK severity IN (INFO, WARNING, CRITICAL); index (recipient, is_read, created_at) |
| `condonation_requests` | student, optional subject, reason, `document_path` (reserved), status, `attendance_at_request`, `reviewed_by`, `review_comment`, created/updated/reviewed timestamps | CHECK status IN (PENDING, APPROVED, REJECTED, WITHDRAWN); **partial UNIQUE (student, COALESCE(subject,0)) WHERE status = 'PENDING'** |
| `condonation_events` | request, actor, from_status, to_status, comment, created_at | append-only decision history |

Indexes beyond the unique constraints: `students(department_id)`, `students(mentor_id)`,
`subjects(department_id)`, `attendance_records(student_id, date)`,
`attendance_records(subject_id)`, `projections(risk_level)`,
`condonation_requests(status, created_at)`, `condonation_requests(student_id)`,
`sessions(user_id)`.

## Design notes

* **Students vs users**: a student record can exist without a login (for example when registered by an
  import). A login links to at most one student.
* **Attendance rows are periods**, not single lectures: `date` is the period end, counts are the
  classes in that period. Duplicates are prevented by the unique key, and the importer reports them
  per row before the database would reject them.
* **Projections are a cache** of the analytics engine output, rewritten in the same transaction
  as the import that changed the data, so dashboards never show half-updated figures.
* **Seed data** (`python -m app.seed`) is fictional: 2 departments, 6 subjects, 14 students,
  6 staff/demo accounts. Attendance history is loaded through the real import pipeline.
