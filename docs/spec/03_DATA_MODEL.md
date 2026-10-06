# AttendAI — Data Model

## users

```text
id
name
email UNIQUE
password_hash
role
created_at
updated_at
```

Roles:

```text
STUDENT
MENTOR
ADMIN
EXAM_CELL
```

## departments

```text
id
name UNIQUE
```

## students

```text
id
user_id FK users
roll_number UNIQUE
department_id FK departments
semester
mentor_id nullable
```

## subjects

```text
id
name
department_id FK departments
code
```

## attendance

```text
id
student_id FK students
subject_id FK subjects
classes_conducted
classes_attended
date
```

Recommended uniqueness:

```text
student + subject + date
```

## projections

```text
id
student_id
subject_id nullable
projected_percentage
risk_level
target_percentage
trend
reason
recommended_action
calculated_at
```

## alerts

```text
id
student_id
mentor_id nullable
message
severity
is_read
created_at
```

## condonation_requests

```text
id
student_id
reason
document_path nullable
status
reviewed_by nullable
review_comment nullable
created_at
reviewed_at nullable
```

## Integrity

- attended <= conducted
- conducted >= 0
- attended >= 0
- valid foreign keys
- unique attendance records
- valid role values
- valid request statuses
