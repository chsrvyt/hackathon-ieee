# AttendAI — Analytics Specification (as implemented)

Source: `backend/app/analytics/engine.py` (pure functions) and `backend/app/analytics/service.py`.
Tests: `backend/tests/test_engine.py` (91 cases), `backend/tests/test_analytics_api.py`.

All arithmetic uses exact rational numbers (`fractions.Fraction`). Values are converted to
percentages (2 decimals) only for output, so boundaries such as "exactly 75%" and the
minimum recovery count are never off by one because of floating-point error.

**Nothing here is machine learning.** It is transparent arithmetic over recorded attendance.

## Data unit

Each attendance record is *(student, subject, date, classes_conducted, classes_attended)*:
the classes held and attended in the reporting period **ending** on `date` (one day or a
longer period). Totals are sums over records. A student's subjects are the subjects that
appear in their records.

## Policy (environment variables)

| Setting | Default | Meaning |
|---|---|---|
| `TARGET_PERCENTAGE` | 75 | minimum required attendance (overall and per subject) |
| `WARNING_BAND_POINTS` | 5 | projected within this many points above target → WARNING |
| `TREND_RECENT_PERIODS` | 2 | number of most-recent reporting periods in the "recent" window |
| `TREND_THRESHOLD_POINTS` | 5 | change needed to call a trend improving/decreasing |
| `DEFAULT_PLANNED_CLASSES` | 60 | classes planned per subject per term when a subject has no `planned_classes` |

## 1. Current attendance

`current = A / C` for attended `A`, conducted `C`. If `C = 0` the result is **null**
(no division, no invented percentage). Overall attendance = Σattended / Σconducted.

## 2. Trend

Records are aggregated per date. The **recent window** is the last `TREND_RECENT_PERIODS`
distinct dates; the **previous window** is every earlier date.

```
change = recent% − previous%
change ≥ +threshold → IMPROVING
change ≤ −threshold → DECREASING
otherwise           → STABLE
no previous window  → INSUFFICIENT_DATA
```

## 3. Projection (end of term)

```
remaining (per subject) = max(planned_classes − conducted, 0)
rate                    = recent-window attendance rate (or the overall rate if there is no history)
projected               = (A + rate × remaining) / (C + remaining)
```

The overall projection uses the overall recent rate and the sum of per-subject remaining
classes. With no remaining classes, projected = current.

*Assumption, displayed to users:* "continue the recent attendance rate for the remaining
planned classes". This is a scenario, not a forecast with a measured accuracy.

## 4. Risk classification

Evaluated for the overall figures and for every subject:

| Level | Rule |
|---|---|
| `NO_DATA` | no classes conducted |
| `CRITICAL` | projected < target |
| `WARNING` | projected < target + band, **or** current < target, **or** a *material* decline: trend DECREASING **and** the recent rate itself < target + band |
| `SAFE` | otherwise |

The student's level is the **worst** of the overall level and every subject level (a
subject shortage matters even when the overall figure is fine). The reason names the
driving subject in that case.

Why "material decline" needs the recent rate inside the band: a drop from 100% to 95% is
a decrease, but flagging it would bury mentors in noise. A drop from 92% to 72% is flagged.

Every result exposes `current_percentage`, `target_percentage`, `trend` (+ the windows and
the change), `projected_percentage`, `risk_level`, `risk_rules`, `reason`,
`recommended_action`, the projection inputs and the recovery plan.

## 5. Recovery calculator

Minimum integer `X ≥ 0` (consecutive classes attended) such that

```
(A + X) / (C + X) ≥ T
X = ceil((T·C − A) / (1 − T))        for T < 1
```

* already at/above target → `X = 0`, status `ALREADY_MET`, plus **buffer** `Y = floor(A/T − C)`
  (classes that could be missed while staying at/above target)
* `T = 100%` and any absence → `UNREACHABLE` (no X exists, none is invented)
* `X > remaining classes this term` → `NOT_RECOVERABLE_THIS_TERM`, with the best possible
  end-of-term percentage `(A + remaining) / (C + remaining)`; the recommended action is the
  condonation route
* `C = 0` → `NO_DATA`
* also reported: `classes_needed_of_remaining = ceil(T·(C + remaining) − A)`, the minimum
  number of the remaining classes to attend to *finish* the term at the target

The implementation asserts minimality for every result:
`(A+X)/(C+X) ≥ T` and `(A+X−1)/(C+X−1) < T`. Worked example: A=72, C=100, T=75% → X=12
(84/112 = 75.0%).

## 6. Explanations

Reason and action strings are generated from the triggered rules with the actual numbers,
for example:

> Projected attendance of 72.8% is below the 75% target, assuming the recent rate of 70.1%
> over the last 2 periods continues for the 87 remaining classes. Current attendance is
> 74.5%. Recent attendance fell from 81% to 70.1%.
>
> Next step: Attend the next 3 classes without an absence to return to 75%, and at least 66
> of the 87 remaining classes to finish the term above the target.

## 7. Snapshots and alerts

After every successful import (in the same database transaction) the affected students'
analytics are recomputed and stored in `projections` (one overall row + one row per subject).
Dashboards, lists and reports read these indexed rows. Student detail pages compute live.
When a student's overall level changes to WARNING/CRITICAL, an alert is created for the student
and their mentor. A change back to SAFE notifies the student. `POST /api/analytics/recompute`
refreshes all snapshots (for example after a policy change).

## 8. Limitations

* Early-warning decision support only. It does not guarantee future attendance and does not rule on
  examination eligibility (no institutional eligibility rules are encoded).
* Planned classes per subject must be configured (seeded) for accurate "remaining classes".
* The projection assumes the recent rate continues. It does not model timetables, holidays or
  medical leave.
* No predictive accuracy is claimed, because no historical outcome data was available to validate against.
