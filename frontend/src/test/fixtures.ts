import type { Analysis, StudentAnalytics } from "../api/types";

const base: Analysis = {
  label: "Overall",
  classes_attended: 108,
  classes_conducted: 145,
  current_percentage: 74.48,
  target_percentage: 75,
  projected_percentage: 72.84,
  trend: "DECREASING",
  trend_detail: {
    direction: "DECREASING",
    recent_percentage: 70.11,
    previous_percentage: 81.03,
    change_points: -10.92,
    recent_window: ["2026-08-17", "2026-09-01"],
    previous_window: ["2026-07-20", "2026-08-03"],
  },
  risk_level: "CRITICAL",
  risk_rules: ["PROJECTED_BELOW_TARGET"],
  reason: "Projected attendance of 72.8% is below the 75% target.",
  recommended_action: "Attend the next 3 classes without an absence to return to 75%.",
  projection: {
    method: "Deterministic",
    rate_used_percentage: 70.11,
    planned_classes: 232,
    remaining_classes: 87,
    formula: "(attended + rate x remaining) / (conducted + remaining)",
  },
  recovery: {
    status: "RECOVERABLE",
    possible: true,
    classes_required: 3,
    remaining_classes: 87,
    classes_needed_of_remaining: 66,
    max_achievable_percentage: 84.05,
    buffer_classes: 0,
    message: "Attend the next 3 classes without an absence to reach 75% (111/148).",
  },
};

export function analyticsFixture(overrides: Partial<StudentAnalytics> = {}): StudentAnalytics {
  return {
    student_id: 3,
    student: {
      id: 3,
      roll_number: "S003",
      name: "Rohan Verma",
      semester: 2,
      department: { id: 1, code: "CSE", name: "Computer Science & Engineering" },
      mentor: { id: 3, name: "Prof. Kavita Rao" },
    },
    current_percentage: base.current_percentage,
    projected_percentage: base.projected_percentage,
    target_percentage: 75,
    risk_level: "CRITICAL",
    trend: "DECREASING",
    reason: base.reason,
    recommended_action: base.recommended_action,
    recovery: base.recovery,
    overall: base,
    subjects: [
      {
        ...base,
        label: "Operating Systems",
        classes_attended: 36,
        classes_conducted: 50,
        current_percentage: 72,
        projected_percentage: 70,
        subject: { id: 3, code: "CS103", name: "Operating Systems" },
      },
    ],
    timeline: [
      { date: "2026-08-17", conducted: 29, attended: 22, period_percentage: 75.86, cumulative_percentage: 79.31 },
      { date: "2026-09-01", conducted: 58, attended: 39, period_percentage: 67.24, cumulative_percentage: 74.48 },
    ],
    policy: { target_percentage: 75, warning_band_points: 5, trend_recent_periods: 2, trend_threshold_points: 5 },
    disclaimer: "Decision-support estimate. It is not a guarantee of future attendance.",
    ...overrides,
  };
}
