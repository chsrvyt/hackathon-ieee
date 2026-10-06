# AttendAI — Analytics Specification

## 1. Current Attendance

For attended A and conducted C:

```text
percentage = A / C * 100
```

If C = 0:

```text
percentage = null
```

Do not invent a percentage.

## 2. Recovery Calculator

Given:

```text
A = classes attended
C = classes conducted
T = target percentage as decimal
X = future classes attended
```

Need minimum integer X satisfying:

```text
(A + X) / (C + X) >= T
```

For T < 1:

```text
X >= (T*C - A) / (1-T)
```

Round upward.

If already at/above target:

```text
X = 0
```

If target >= 100 and current attendance < 100:

```text
unreachable through ordinary future attendance
```

## 3. Trend

Use a simple explainable recent trend.

Possible implementation:

```text
recent attendance percentage
minus
previous attendance percentage
```

Classify:

```text
positive → IMPROVING
near zero → STABLE
negative → DECREASING
```

Document the exact window used by implementation.

## 4. Projection

The MVP may use a deterministic projection rather than ML.

The projection must document:
- input window
- future class assumption
- calculation
- limitations

Never label deterministic arithmetic as "AI prediction" unless an actual validated ML model is used.

## 5. Risk

Risk levels:

```text
SAFE
WARNING
CRITICAL
```

Thresholds configurable.

Recommended baseline:

```text
CRITICAL:
projected < target

WARNING:
projected is within configured warning band of target OR trend is materially decreasing

SAFE:
otherwise
```

The exact implementation must be documented and tested.

## 6. Explainability

Every risk result must answer:

```text
What is the current attendance?
What is the target?
What is the projected attendance?
What trend was detected?
Why is the student classified this way?
What should the student do next?
```

## 7. Limitations

The prototype is an early-warning decision-support system.

It must not claim:
- guaranteed future attendance
- medical eligibility
- examination eligibility unless official institutional rules are explicitly encoded
- predictive accuracy without validation
