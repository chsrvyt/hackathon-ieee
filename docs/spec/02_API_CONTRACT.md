# AttendAI — API Contract

Base path:

```text
/api
```

## Health

```http
GET /health
```

Response:

```json
{"status":"ok"}
```

## Authentication

```http
POST /auth/login
```

Request:

```json
{
  "email": "student@example.com",
  "password": "password"
}
```

Response should contain authenticated user identity and role.

```http
POST /auth/logout
GET /auth/me
```

## Attendance

```http
POST /attendance/upload
GET /attendance/student/{student_id}
GET /attendance/subject/{subject_id}
```

Upload must support CSV/XLSX and return:

```json
{
  "success": true,
  "rows_processed": 100,
  "rows_rejected": 0,
  "errors": []
}
```

## Analytics

```http
GET /analytics/student/{student_id}
GET /analytics/risk-students
GET /analytics/department/{department_id}
```

Student analytics should expose:

```json
{
  "current_percentage": 72,
  "projected_percentage": 69,
  "target_percentage": 75,
  "risk_level": "CRITICAL",
  "trend": "DECREASING",
  "reason": "...",
  "recommended_action": "...",
  "recovery": {
    "possible": true,
    "classes_required": 12
  }
}
```

## Alerts

```http
GET /alerts
PATCH /alerts/{id}/read
```

## Condonation

```http
POST /condonation
GET /condonation/student/{student_id}
GET /condonation/pending
PATCH /condonation/{id}/decision
```

Decision:

```json
{
  "decision": "APPROVED",
  "comment": "..."
}
```

## Error contract

Prefer:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Attendance cannot exceed conducted classes.",
    "details": []
  }
}
```

Do not expose internal stack traces.

## Authorization

Every endpoint must enforce server-side role and ownership checks.
