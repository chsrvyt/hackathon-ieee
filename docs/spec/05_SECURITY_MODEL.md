# AttendAI — Security Model

## Authentication

- Passwords must be hashed using a modern password hashing algorithm.
- Never store plaintext passwords.
- Sessions/tokens must expire.
- Logout must invalidate the active session where applicable.

## Authorization

Server-side authorization is mandatory.

### Student

May access:
- own profile
- own attendance
- own analytics
- own alerts
- own condonation requests

### Mentor

May access:
- assigned students
- authorized risk information
- relevant condonation requests

### Admin/HOD

May access:
- department analytics
- reporting
- authorized student/mentor information
- condonation review

### Exam Cell

May access:
- shortage and eligibility reporting
- condonation decision information

## Upload Security

Validate:
- extension
- MIME type where practical
- file size
- required columns
- data types
- numeric ranges
- duplicate records

Never execute uploaded files.

## API Security

- Validate all request bodies.
- Validate IDs.
- Do not trust role values sent by the frontend.
- Prevent IDOR/BOLA vulnerabilities.
- Use ORM/parameterized queries.
- Restrict CORS in production.
- Return generic production errors.
- Do not log passwords/tokens.

## Secrets

Environment variables only.

Required examples:

```text
DATABASE_URL=
SECRET_KEY=
FRONTEND_ORIGIN=
```

Never commit `.env`.

## Production checklist

- HTTPS
- secure auth configuration
- production CORS
- database backups where available
- least-privilege database credentials
- dependency audit
- no debug mode
