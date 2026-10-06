"""Unit tests for the pure analytics engine (no database)."""

from datetime import date
from fractions import Fraction

import pytest

from app.analytics.engine import (
    Period,
    Policy,
    analyze,
    attendance_percentage,
    attendance_ratio,
    buffer_classes,
    classes_required,
    classify,
    compute_trend,
    project,
    recovery_plan,
    worst,
)

T75 = Fraction(3, 4)
POLICY = Policy.from_percentages(75, 5, 2, 5)


# --- current attendance ------------------------------------------------------


@pytest.mark.parametrize(
    ("attended", "conducted", "expected"),
    [(0, 10, 0.0), (5, 10, 50.0), (10, 10, 100.0), (72, 100, 72.0), (3, 4, 75.0), (2, 3, 66.67)],
)
def test_attendance_percentage(attended, conducted, expected):
    assert attendance_percentage(attended, conducted) == expected


def test_zero_conducted_returns_none_not_division_error():
    assert attendance_ratio(0, 0) is None
    assert attendance_percentage(0, 0) is None


@pytest.mark.parametrize(("attended", "conducted"), [(11, 10), (-1, 10), (1, -1)])
def test_invalid_counts_rejected(attended, conducted):
    with pytest.raises(ValueError):
        attendance_ratio(attended, conducted)


# --- recovery ------------------------------------------------------------------


def _check_minimal(a, c, t, x):
    assert Fraction(a + x, c + x) >= t
    if x > 0:
        assert Fraction(a + x - 1, c + x - 1) < t


def test_recovery_spec_example_72_of_100():
    x = classes_required(72, 100, T75)
    assert x == 12  # (72+12)/(100+12) = 84/112 = 0.75 exactly
    _check_minimal(72, 100, T75, x)


def test_recovery_exactly_at_target_needs_zero():
    assert classes_required(75, 100, T75) == 0
    assert classes_required(3, 4, T75) == 0


def test_recovery_already_above_target():
    assert classes_required(90, 100, T75) == 0
    plan = recovery_plan(90, 100, T75, remaining=20)
    assert plan.status == "ALREADY_MET" and plan.possible
    assert plan.buffer_classes == 20  # 90/120 = 0.75


def test_recovery_very_low_attendance():
    x = classes_required(10, 100, T75)
    assert x == 260
    _check_minimal(10, 100, T75, x)


def test_recovery_target_100_percent_is_unreachable_after_any_absence():
    assert classes_required(99, 100, Fraction(1)) is None
    assert classes_required(100, 100, Fraction(1)) == 0
    plan = recovery_plan(99, 100, Fraction(1), remaining=50)
    assert plan.status == "UNREACHABLE" and not plan.possible


def test_recovery_zero_conducted():
    assert classes_required(0, 0, T75) == 0
    plan = recovery_plan(0, 0, T75, remaining=40)
    assert plan.status == "NO_DATA"


def test_recovery_not_possible_within_remaining_term():
    plan = recovery_plan(30, 60, T75, remaining=20)  # needs 60 consecutive; only 20 left
    assert plan.status == "NOT_RECOVERABLE_THIS_TERM"
    assert not plan.possible
    assert plan.classes_required == 60
    assert plan.max_achievable_percentage == 62.5  # 50/80


@pytest.mark.parametrize("a", range(0, 101, 7))
@pytest.mark.parametrize("t", [Fraction(3, 4), Fraction(2, 3), Fraction(4, 5), Fraction(17, 20)])
def test_recovery_is_always_minimal(a, t):
    x = classes_required(a, 100, t)
    _check_minimal(a, 100, t, x)


def test_buffer_classes():
    assert buffer_classes(80, 100, T75) == 6  # 80/106 >= .75, 80/107 < .75
    assert buffer_classes(70, 100, T75) == 0


# --- trend ----------------------------------------------------------------------


def _periods(*rows):
    return [Period(date(2026, 7, 1 + i * 7), c, a) for i, (c, a) in enumerate(rows)]


def test_trend_decreasing():
    t = compute_trend(_periods((10, 9), (10, 9), (10, 6), (10, 6)), POLICY)
    assert t.direction == "DECREASING"
    assert t.previous_ratio == Fraction(9, 10) and t.recent_ratio == Fraction(6, 10)


def test_trend_improving():
    assert compute_trend(_periods((10, 5), (10, 6), (10, 9), (10, 10)), POLICY).direction == "IMPROVING"


def test_trend_stable_within_threshold():
    assert compute_trend(_periods((10, 8), (10, 8), (10, 8), (20, 15)), POLICY).direction == "STABLE"


def test_trend_no_history():
    t = compute_trend(_periods((20, 14)), POLICY)
    assert t.direction == "INSUFFICIENT_DATA"
    assert compute_trend([], POLICY).direction == "INSUFFICIENT_DATA"


def test_trend_aggregates_subjects_on_same_date():
    d = date(2026, 9, 1)
    t = compute_trend([Period(d, 10, 5), Period(d, 10, 10)], POLICY)
    assert t.recent_ratio == Fraction(15, 20)


# --- projection & risk -----------------------------------------------------------


def test_projection_continues_recent_rate():
    # 72/100 so far, recent rate 60 %, 40 classes left -> (72 + 24) / 140
    assert project(72, 100, Fraction(3, 5), 40) == Fraction(96, 140)


def test_projection_no_remaining_classes_equals_current():
    assert project(72, 100, Fraction(1, 2), 0) == Fraction(72, 100)


def test_projection_no_data():
    assert project(0, 0, None, 40) is None


def test_classify_boundaries():
    assert classify(T75, T75, "STABLE", POLICY)[0] == "WARNING"  # at target -> inside warning band
    assert classify(T75, Fraction(80, 100), "STABLE", POLICY)[0] == "SAFE"  # exactly target + band
    assert classify(T75, Fraction(7499, 10000), "STABLE", POLICY)[0] == "CRITICAL"
    # A decline only matters once the recent rate is inside the warning band.
    assert classify(Fraction(9, 10), Fraction(9, 10), "DECREASING", POLICY, Fraction(78, 100))[0] == "WARNING"
    assert classify(Fraction(9, 10), Fraction(9, 10), "DECREASING", POLICY, Fraction(95, 100))[0] == "SAFE"
    assert classify(Fraction(7, 10), Fraction(8, 10), "IMPROVING", POLICY) == ("WARNING", ["CURRENT_BELOW_TARGET"])
    assert classify(None, None, "INSUFFICIENT_DATA", POLICY)[0] == "NO_DATA"


def test_analyze_critical_case_is_explained():
    a = analyze("Overall", _periods((25, 20), (25, 19), (25, 18), (25, 15)), planned_classes=140, policy=POLICY)
    out = a.to_dict()
    assert out["current_percentage"] == 72.0
    assert out["trend"] == "DECREASING"
    assert out["risk_level"] == "CRITICAL"
    assert out["projected_percentage"] < 75
    assert "below the 75.0% target" in out["reason"]
    assert out["recovery"]["classes_required"] == 12
    assert "next 12 classes" in out["recommended_action"]
    for key in (
        "current_percentage",
        "target_percentage",
        "trend",
        "projected_percentage",
        "risk_level",
        "reason",
        "recommended_action",
    ):
        assert out[key] is not None


def test_analyze_safe_case():
    a = analyze("DBMS", _periods((10, 10), (10, 9), (10, 10)), planned_classes=60, policy=POLICY)
    assert a.risk_level == "SAFE"
    assert "comfortably above" in a.reason


def test_analyze_unrecoverable_recommends_condonation():
    a = analyze("OS", _periods((20, 8), (20, 8), (20, 8)), planned_classes=70, policy=POLICY)
    assert a.risk_level == "CRITICAL"
    assert not a.recovery.possible
    assert "condonation" in a.recommended_action


def test_worst():
    assert worst(["SAFE", "CRITICAL", "WARNING"]) == "CRITICAL"
    assert worst([]) == "NO_DATA"
