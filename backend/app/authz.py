"""Server-side authorization scopes. Every data-returning endpoint goes through these helpers.

STUDENT    -> own student record only
MENTOR     -> students whose mentor_id is the mentor
ADMIN      -> department_id NULL: whole institution; otherwise only that department (HOD)
EXAM_CELL  -> read-only, institution-wide shortage/eligibility reporting
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, false, true

from .errors import AppError, forbidden
from .models import CondonationRequest, Student, User

STAFF_ROLES = ("MENTOR", "ADMIN", "EXAM_CELL")
REPORT_ROLES = ("ADMIN", "EXAM_CELL")
REVIEWER_ROLES = ("MENTOR", "ADMIN")


def student_scope(user: User) -> ColumnElement[bool]:
    """SQL condition restricting `Student` rows to those the user may see."""
    if user.role == "ADMIN":
        return true() if user.department_id is None else Student.department_id == user.department_id
    if user.role == "EXAM_CELL":
        return true()
    if user.role == "MENTOR":
        return Student.mentor_id == user.id
    if user.role == "STUDENT":
        return Student.user_id == user.id
    return false()


def can_view_student(user: User, student: Student) -> bool:
    if user.role == "ADMIN":
        return user.department_id is None or student.department_id == user.department_id
    if user.role == "EXAM_CELL":
        return True
    if user.role == "MENTOR":
        return student.mentor_id == user.id
    if user.role == "STUDENT":
        return student.user_id is not None and student.user_id == user.id
    return False


def ensure_can_view_student(user: User, student: Student) -> None:
    if not can_view_student(user, student):
        raise forbidden("You are not authorised to view this student's records.")


def can_view_department(user: User, department_id: int) -> bool:
    if user.role == "EXAM_CELL":
        return True
    if user.role == "ADMIN":
        return user.department_id is None or user.department_id == department_id
    return False


def ensure_can_view_department(user: User, department_id: int) -> None:
    if not can_view_department(user, department_id):
        raise forbidden("You are not authorised to view this department's report.")


def ensure_can_review(user: User, request: CondonationRequest) -> None:
    if user.role not in REVIEWER_ROLES:
        raise forbidden("Only the assigned mentor or an administrator can review condonation requests.")
    student = request.student
    if user.role == "MENTOR" and student.mentor_id != user.id:
        raise forbidden("You can only review requests from students assigned to you.")
    if user.role == "ADMIN" and user.department_id is not None and student.department_id != user.department_id:
        raise forbidden("This request belongs to a department outside your scope.")
    if student.user_id is not None and student.user_id == user.id:
        raise AppError(403, "FORBIDDEN", "You cannot review your own request.")
