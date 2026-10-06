"""Deterministic, explainable attendance analytics.

Pure functions only: no database, no I/O. All arithmetic is exact (fractions.Fraction),
so boundary cases such as "exactly 75%" and the minimum recovery count are never off
by one because of floating-point rounding. Values are converted to floats (percent,
2 decimals) only when building output.

Nothing here is machine learning. The projection is: "if the student keeps attending
at their recent rate for the remaining planned classes, where do they finish?".
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from fractions import Fraction

SEVERITY = {"NO_DATA": 0, "SAFE": 1, "WARNING": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class Policy:
    target: Fraction  # e.g. Fraction(3, 4) for 75 %
    warning_band: Fraction  # e.g. Fraction(1, 20) for 5 percentage points
    trend_recent_periods: int  # how many most-recent periods form the "recent" window
    trend_threshold: Fraction  # change (as a ratio) needed to call a trend improving/decreasing

    @classmethod
    def from_percentages(
        cls,
        target: Decimal | int | str = 75,
        warning_band: Decimal | int | str = 5,
        trend_recent_periods: int = 2,
        trend_threshold: Decimal | int | str = 5,
    ) -> Policy:
        return cls(
            target=percent_to_ratio(target),
            warning_band=percent_to_ratio(warning_band),
            trend_recent_periods=trend_recent_periods,
            trend_threshold=percent_to_ratio(trend_threshold),
        )

    @property
    def target_percentage(self) -> float:
        return as_percentage(self.target)  # type: ignore[return-value]


@dataclass(frozen=True)
class Period:
    """Classes conducted/attended in one reporting period (identified by its end date)."""

    date: date
    conducted: int
    attended: int


def percent_to_ratio(value: Decimal | int | str | float) -> Fraction:
    return Fraction(Decimal(str(value))) / 100


def as_percentage(ratio: Fraction | None) -> float | None:
    if ratio is None:
        return None
    return round(float(ratio * 100), 2)


def fmt(ratio: Fraction | None) -> str:
    value = as_percentage(ratio)
    if value is None:
        return "n/a"
    text = f"{value:.1f}"
    return f"{text}%"


def _validate_counts(attended: int, conducted: int) -> None:
    if attended < 0 or conducted < 0:
        raise ValueError("Attendance counts cannot be negative.")
    if attended > conducted:
        raise ValueError("Classes attended cannot exceed classes conducted.")


# ---------------------------------------------------------------------------
# 1. Current attendance
# ---------------------------------------------------------------------------


def attendance_ratio(attended: int, conducted: int) -> Fraction | None:
    """attended / conducted, or None when no classes were conducted (never divides by zero)."""
    _validate_counts(attended, conducted)
    if conducted == 0:
        return None
    return Fraction(attended, conducted)


def attendance_percentage(attended: int, conducted: int) -> float | None:
    return as_percentage(attendance_ratio(attended, conducted))


# ---------------------------------------------------------------------------
# 2. Recovery calculator
# ---------------------------------------------------------------------------


def classes_required(attended: int, conducted: int, target: Fraction) -> int | None:
    """Minimum integer X >= 0 with (A + X) / (C + X) >= T, or None when no X exists.

    For T < 1: X = ceil((T*C - A) / (1 - T)). For T = 1 the target is reachable only if
    the student has never missed a class.
    """
    _validate_counts(attended, conducted)
    if not (0 < target <= 1):
        raise ValueError("Target must be in (0, 1].")
    if conducted == 0 or Fraction(attended, conducted) >= target:
        return 0
    if target == 1:
        return None
    x = math.ceil((target * conducted - attended) / (1 - target))
    # Self-check: X satisfies the inequality and X - 1 does not (minimality).
    assert Fraction(attended + x, conducted + x) >= target
    assert x == 0 or Fraction(attended + x - 1, conducted + x - 1) < target
    return x


def buffer_classes(attended: int, conducted: int, target: Fraction) -> int:
    """Largest Y >= 0 such that missing the next Y classes keeps A / (C + Y) >= T."""
    _validate_counts(attended, conducted)
    if conducted == 0 or Fraction(attended, conducted) < target:
        return 0
    return max(0, math.floor(Fraction(attended) / target - conducted))


def classes_needed_of_remaining(attended: int, conducted: int, remaining: int, target: Fraction) -> int:
    """Minimum classes to attend out of `remaining` to finish the term at/above target (may exceed remaining)."""
    return max(0, math.ceil(target * (conducted + remaining) - attended))


@dataclass
class Recovery:
    status: str  # NO_DATA | ALREADY_MET | RECOVERABLE | NOT_RECOVERABLE_THIS_TERM | UNREACHABLE
    possible: bool
    classes_required: int | None
    remaining_classes: int
    classes_needed_of_remaining: int | None
    max_achievable_percentage: float | None
    buffer_classes: int
    message: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def recovery_plan(attended: int, conducted: int, target: Fraction, remaining: int) -> Recovery:
    _validate_counts(attended, conducted)
    remaining = max(0, remaining)
    target_txt = fmt(target)
    total = conducted + remaining
    max_ratio = Fraction(attended + remaining, total) if total else None
    needed = classes_needed_of_remaining(attended, conducted, remaining, target) if total else None

    if conducted == 0:
        return Recovery(
            "NO_DATA",
            True,
            0,
            remaining,
            needed,
            as_percentage(max_ratio),
            0,
            "No classes have been conducted yet, so there is nothing to recover.",
        )

    x = classes_required(attended, conducted, target)
    current = Fraction(attended, conducted)
    buffer = buffer_classes(attended, conducted, target)

    if current >= target:
        message = f"Already at or above the {target_txt} target."
        if buffer:
            message += f" The current buffer is {buffer} class{'es' if buffer != 1 else ''} above the minimum."
        else:
            message += " There is no buffer: missing the next class would drop attendance below the target."
        return Recovery("ALREADY_MET", True, 0, remaining, needed, as_percentage(max_ratio), buffer, message)

    if x is None:
        return Recovery(
            "UNREACHABLE",
            False,
            None,
            remaining,
            needed,
            as_percentage(max_ratio),
            0,
            f"A {target_txt} target cannot be reached once any class has been missed.",
        )

    if x > remaining:
        return Recovery(
            "NOT_RECOVERABLE_THIS_TERM",
            False,
            x,
            remaining,
            needed,
            as_percentage(max_ratio),
            0,
            f"{x} consecutive classes would be needed but only {remaining} remain this term; "
            f"attending all of them reaches at most {fmt(max_ratio)}.",
        )

    return Recovery(
        "RECOVERABLE",
        True,
        x,
        remaining,
        needed,
        as_percentage(max_ratio),
        0,
        f"Attend the next {x} class{'es' if x != 1 else ''} without an absence to reach {target_txt} "
        f"({attended + x}/{conducted + x}).",
    )


# ---------------------------------------------------------------------------
# 3. Trend
# ---------------------------------------------------------------------------


def aggregate_by_date(periods: Iterable[Period]) -> list[Period]:
    totals: OrderedDict[date, list[int]] = OrderedDict()
    for p in sorted(periods, key=lambda p: p.date):
        bucket = totals.setdefault(p.date, [0, 0])
        bucket[0] += p.conducted
        bucket[1] += p.attended
    return [Period(d, c, a) for d, (c, a) in totals.items()]


@dataclass
class Trend:
    direction: str  # IMPROVING | STABLE | DECREASING | INSUFFICIENT_DATA
    recent_ratio: Fraction | None
    previous_ratio: Fraction | None
    recent_periods: list[date] = field(default_factory=list)
    previous_periods: list[date] = field(default_factory=list)

    @property
    def delta(self) -> Fraction | None:
        if self.recent_ratio is None or self.previous_ratio is None:
            return None
        return self.recent_ratio - self.previous_ratio

    def to_dict(self) -> dict:
        delta = self.delta
        return {
            "direction": self.direction,
            "recent_percentage": as_percentage(self.recent_ratio),
            "previous_percentage": as_percentage(self.previous_ratio),
            "change_points": None if delta is None else round(float(delta * 100), 2),
            "recent_window": [d.isoformat() for d in self.recent_periods],
            "previous_window": (
                [self.previous_periods[0].isoformat(), self.previous_periods[-1].isoformat()]
                if self.previous_periods
                else []
            ),
        }


def compute_trend(periods: Iterable[Period], policy: Policy) -> Trend:
    """Recent window = the last N reporting periods; previous window = every earlier period.

    trend change = recent attendance % - previous attendance %
      >= +threshold -> IMPROVING, <= -threshold -> DECREASING, otherwise STABLE.
    With no earlier periods the trend is INSUFFICIENT_DATA.
    """
    series = aggregate_by_date(periods)
    k = policy.trend_recent_periods
    recent, previous = series[-k:], series[:-k]
    recent_c = sum(p.conducted for p in recent)
    prev_c = sum(p.conducted for p in previous)
    recent_ratio = Fraction(sum(p.attended for p in recent), recent_c) if recent_c else None
    previous_ratio = Fraction(sum(p.attended for p in previous), prev_c) if prev_c else None
    dates_recent = [p.date for p in recent]
    dates_prev = [p.date for p in previous]
    if recent_ratio is None or previous_ratio is None:
        return Trend("INSUFFICIENT_DATA", recent_ratio, previous_ratio, dates_recent, dates_prev)
    delta = recent_ratio - previous_ratio
    if delta >= policy.trend_threshold:
        direction = "IMPROVING"
    elif delta <= -policy.trend_threshold:
        direction = "DECREASING"
    else:
        direction = "STABLE"
    return Trend(direction, recent_ratio, previous_ratio, dates_recent, dates_prev)


# ---------------------------------------------------------------------------
# 4. Projection
# ---------------------------------------------------------------------------


def project(attended: int, conducted: int, rate: Fraction | None, remaining: int) -> Fraction | None:
    """End-of-term attendance if the student attends `rate` of the `remaining` classes."""
    _validate_counts(attended, conducted)
    remaining = max(0, remaining)
    if rate is None:
        rate = Fraction(attended, conducted) if conducted else None
    if rate is None:
        return None
    if conducted + remaining == 0:
        return None
    return (attended + rate * remaining) / (conducted + remaining)


# ---------------------------------------------------------------------------
# 5 + 6. Risk classification and explanation
# ---------------------------------------------------------------------------


def classify(
    current: Fraction | None,
    projected: Fraction | None,
    trend: str,
    policy: Policy,
    recent: Fraction | None = None,
) -> tuple[str, list[str]]:
    """Return (risk level, triggered rule codes).

    CRITICAL : projected < target
    WARNING  : projected < target + band, or current < target, or a material decline
               (trend DECREASING and the recent rate itself is below target + band)
    SAFE     : otherwise
    NO_DATA  : nothing conducted yet
    """
    if current is None or projected is None:
        return "NO_DATA", ["NO_DATA"]
    if projected < policy.target:
        return "CRITICAL", ["PROJECTED_BELOW_TARGET"]
    rules = []
    if current < policy.target:
        rules.append("CURRENT_BELOW_TARGET")
    if projected < policy.target + policy.warning_band:
        rules.append("PROJECTED_NEAR_TARGET")
    if trend == "DECREASING" and (recent is None or recent < policy.target + policy.warning_band):
        rules.append("DECREASING_TREND")
    return ("WARNING", rules) if rules else ("SAFE", ["ON_TRACK"])


@dataclass
class Analysis:
    label: str
    attended: int
    conducted: int
    planned_classes: int
    remaining_classes: int
    current: Fraction | None
    projected: Fraction | None
    rate_used: Fraction | None
    trend: Trend
    risk_level: str
    rules: list[str]
    reason: str
    recommended_action: str
    recovery: Recovery
    policy: Policy

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "classes_attended": self.attended,
            "classes_conducted": self.conducted,
            "current_percentage": as_percentage(self.current),
            "target_percentage": as_percentage(self.policy.target),
            "projected_percentage": as_percentage(self.projected),
            "trend": self.trend.direction,
            "trend_detail": self.trend.to_dict(),
            "risk_level": self.risk_level,
            "risk_rules": self.rules,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "projection": {
                "method": "Deterministic: continue the recent attendance rate for the remaining planned classes.",
                "rate_used_percentage": as_percentage(self.rate_used),
                "planned_classes": self.planned_classes,
                "remaining_classes": self.remaining_classes,
                "formula": "(attended + rate x remaining) / (conducted + remaining)",
            },
            "recovery": self.recovery.to_dict(),
        }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 'es' if word.endswith('s') else 's'}"


def _explain(a: Analysis) -> tuple[str, str]:
    p, t = a.policy, fmt(a.policy.target)
    rec = a.recovery
    trend = a.trend
    if a.risk_level == "NO_DATA":
        return "No classes have been recorded yet.", "No action needed until attendance is recorded."

    basis = (
        f"the recent rate of {fmt(a.rate_used)} over the last {_plural(len(trend.recent_periods), 'period')}"
        if trend.direction != "INSUFFICIENT_DATA"
        else f"the attendance rate so far ({fmt(a.rate_used)})"
    )
    trend_txt = ""
    if trend.direction in ("DECREASING", "IMPROVING"):
        word = "fell" if trend.direction == "DECREASING" else "rose"
        trend_txt = f" Recent attendance {word} from {fmt(trend.previous_ratio)} to {fmt(trend.recent_ratio)}."

    if a.risk_level == "CRITICAL":
        reason = (
            f"Projected attendance of {fmt(a.projected)} is below the {t} target, assuming {basis} continues "
            f"for the {a.remaining_classes} remaining classes. Current attendance is {fmt(a.current)}." + trend_txt
        )
        if not rec.possible:
            reason += f" Even attending every remaining class reaches only {rec.max_achievable_percentage:.1f}%."
            action = (
                f"The {t} target cannot be reached this term with the remaining classes. Meet your mentor now and "
                "submit a condonation request explaining the absences."
            )
        elif rec.classes_required:
            action = (
                f"Attend the next {_plural(rec.classes_required, 'class')} without an absence to return to {t}, and "
                f"at least {rec.classes_needed_of_remaining} of the {a.remaining_classes} remaining classes to finish "
                "the term above the target. Discuss a recovery plan with your mentor."
            )
        else:
            action = (
                f"Attendance is at the target today but the recent rate would drop it below {t}. Attend at least "
                f"{rec.classes_needed_of_remaining} of the {a.remaining_classes} remaining classes."
            )
        return reason, action

    if a.risk_level == "WARNING":
        parts = []
        if "CURRENT_BELOW_TARGET" in a.rules:
            parts.append(
                f"Current attendance of {fmt(a.current)} is below the {t} target, although the projection at "
                f"{basis} reaches {fmt(a.projected)}."
            )
        if "PROJECTED_NEAR_TARGET" in a.rules and "CURRENT_BELOW_TARGET" not in a.rules:
            parts.append(
                f"Projected attendance of {fmt(a.projected)} is within {fmt(p.warning_band).rstrip('%')} points "
                f"of the {t} target (current {fmt(a.current)})."
            )
        if "DECREASING_TREND" in a.rules:
            parts.append(
                f"Recent attendance fell from {fmt(trend.previous_ratio)} to {fmt(trend.recent_ratio)}, "
                f"close to the {t} line."
            )
        reason = " ".join(parts)
        if rec.classes_required:
            action = (
                f"Attend the next {_plural(rec.classes_required, 'class')} without an absence to get back to {t}, "
                "then keep attending regularly."
            )
        else:
            action = (
                f"Avoid further absences: attend at least {rec.classes_needed_of_remaining} of the "
                f"{a.remaining_classes} remaining classes to stay above {t}."
            )
        return reason, action

    reason = (
        f"Projected attendance of {fmt(a.projected)} is comfortably above the {t} target "
        f"(current {fmt(a.current)}, trend {trend.direction.lower().replace('_', ' ')})."
    )
    action = f"Keep attending regularly. Current buffer: {_plural(rec.buffer_classes, 'class')} above the minimum."
    return reason, action


def analyze(label: str, periods: Iterable[Period], planned_classes: int, policy: Policy) -> Analysis:
    """Full explainable analysis for one subject (or the aggregate of several)."""
    periods = list(periods)
    attended = sum(p.attended for p in periods)
    conducted = sum(p.conducted for p in periods)
    _validate_counts(attended, conducted)
    remaining = max(0, planned_classes - conducted)
    return _build(label, periods, attended, conducted, planned_classes, remaining, policy)


def analyze_overall(
    label: str, periods: Iterable[Period], planned_classes: int, remaining_classes: int, policy: Policy
) -> Analysis:
    """Aggregate analysis where remaining classes are summed per subject by the caller."""
    periods = list(periods)
    attended = sum(p.attended for p in periods)
    conducted = sum(p.conducted for p in periods)
    _validate_counts(attended, conducted)
    return _build(label, periods, attended, conducted, planned_classes, max(0, remaining_classes), policy)


def _build(
    label: str,
    periods: list[Period],
    attended: int,
    conducted: int,
    planned: int,
    remaining: int,
    policy: Policy,
) -> Analysis:
    current = Fraction(attended, conducted) if conducted else None
    trend = compute_trend(periods, policy)
    rate = trend.recent_ratio if trend.recent_ratio is not None else current
    projected = project(attended, conducted, rate, remaining) if conducted else None
    level, rules = classify(current, projected, trend.direction, policy, trend.recent_ratio)
    recovery = recovery_plan(attended, conducted, policy.target, remaining)
    analysis = Analysis(
        label,
        attended,
        conducted,
        planned,
        remaining,
        current,
        projected,
        rate,
        trend,
        level,
        rules,
        "",
        "",
        recovery,
        policy,
    )
    analysis.reason, analysis.recommended_action = _explain(analysis)
    return analysis


def worst(levels: Iterable[str]) -> str:
    return max(levels, key=lambda lvl: SEVERITY[lvl], default="NO_DATA")
