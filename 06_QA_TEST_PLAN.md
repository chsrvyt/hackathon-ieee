# AttendAI — QA Test Plan

## A. Authentication

| ID | Test | Expected |
|---|---|---|
| AUTH-01 | Valid student login | Success |
| AUTH-02 | Invalid password | Rejected |
| AUTH-03 | Unauthenticated dashboard access | Rejected |
| AUTH-04 | Logout | Session invalidated |
| AUTH-05 | Student role | Student scope only |

## B. Attendance

| ID | Test | Expected |
|---|---|---|
| ATT-01 | Valid CSV | Imported |
| ATT-02 | Valid XLSX | Imported |
| ATT-03 | Missing column | Rejected |
| ATT-04 | attended > conducted | Rejected |
| ATT-05 | negative value | Rejected |
| ATT-06 | duplicate row | Rejected/handled |
| ATT-07 | conducted = 0 | No divide-by-zero |
| ATT-08 | 10/10 | 100% |

## C. Analytics

| ID | Test | Expected |
|---|---|---|
| ANA-01 | 5/10 | 50% |
| ANA-02 | 72/100 | 72% |
| ANA-03 | exactly target | Correct boundary |
| ANA-04 | below target projection | CRITICAL |
| ANA-05 | improving trend | Correct trend |
| ANA-06 | declining trend | Correct trend |
| ANA-07 | no history | Safe fallback/error |

## D. Recovery

For:

```text
A=72
C=100
T=0.75
```

minimum X must satisfy:

```text
(72+X)/(100+X) >= 0.75
```

The implementation must verify the result mathematically.

## E. Authorization

- Student cannot access another student's attendance.
- Student cannot approve condonation.
- Mentor cannot access unrelated students.
- Admin can access configured reporting scope.
- Exam Cell cannot mutate unrelated records.

## F. Condonation

- Student submits.
- Status becomes PENDING.
- Reviewer sees request.
- Reviewer approves/rejects.
- Student sees updated status.
- Invalid transitions rejected.

## G. Deployment

- Frontend loads.
- Backend health endpoint responds.
- Frontend API URL is correct.
- Database connection works.
- Upload works in production.
- Authentication works in production.
- No browser console blocker prevents main flow.

## Release gate

No release if a P0 flow is broken.
