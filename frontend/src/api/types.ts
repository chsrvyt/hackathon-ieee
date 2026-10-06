export type Role = "STUDENT" | "MENTOR" | "ADMIN" | "EXAM_CELL";
export type RiskLevel = "SAFE" | "WARNING" | "CRITICAL" | "NO_DATA";
export type Trend = "IMPROVING" | "STABLE" | "DECREASING" | "INSUFFICIENT_DATA";
export type CondonationStatus = "PENDING" | "APPROVED" | "REJECTED" | "WITHDRAWN";

export interface Department {
  id: number;
  code: string;
  name: string;
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  department: Department | null;
  student_id: number | null;
}

export interface Recovery {
  status: "NO_DATA" | "ALREADY_MET" | "RECOVERABLE" | "NOT_RECOVERABLE_THIS_TERM" | "UNREACHABLE";
  possible: boolean;
  classes_required: number | null;
  remaining_classes: number;
  classes_needed_of_remaining: number | null;
  max_achievable_percentage: number | null;
  buffer_classes: number;
  message: string;
}

export interface TrendDetail {
  direction: Trend;
  recent_percentage: number | null;
  previous_percentage: number | null;
  change_points: number | null;
  recent_window: string[];
  previous_window: string[];
}

export interface Analysis {
  label: string;
  classes_attended: number;
  classes_conducted: number;
  current_percentage: number | null;
  target_percentage: number;
  projected_percentage: number | null;
  trend: Trend;
  trend_detail: TrendDetail;
  risk_level: RiskLevel;
  risk_rules: string[];
  reason: string;
  recommended_action: string;
  projection: {
    method: string;
    rate_used_percentage: number | null;
    planned_classes: number;
    remaining_classes: number;
    formula: string;
  };
  recovery: Recovery;
}

export interface SubjectAnalysis extends Analysis {
  subject: { id: number; code: string; name: string };
}

export interface TimelinePoint {
  date: string;
  conducted: number;
  attended: number;
  period_percentage: number | null;
  cumulative_percentage: number | null;
}

export interface StudentAnalytics {
  student_id: number;
  student: {
    id: number;
    roll_number: string;
    name: string;
    semester: number;
    department: Department;
    mentor: { id: number; name: string } | null;
  };
  current_percentage: number | null;
  projected_percentage: number | null;
  target_percentage: number;
  risk_level: RiskLevel;
  trend: Trend;
  reason: string;
  recommended_action: string;
  recovery: Recovery;
  overall: Analysis;
  subjects: SubjectAnalysis[];
  timeline: TimelinePoint[];
  policy: {
    target_percentage: number;
    warning_band_points: number;
    trend_recent_periods: number;
    trend_threshold_points: number;
  };
  disclaimer: string;
}

export interface ProjectionSummary {
  classes_attended: number;
  classes_conducted: number;
  current_percentage: number | null;
  projected_percentage: number | null;
  target_percentage: number;
  trend: Trend;
  risk_level: RiskLevel;
  reason: string;
  recommended_action: string;
  classes_required: number | null;
  recovery_possible: boolean | null;
  calculated_at: string;
}

export interface StudentSummary {
  id: number;
  roll_number: string;
  name: string;
  semester: number;
  department: Department;
  mentor: { id: number; name: string } | null;
  has_account: boolean;
  analytics: ProjectionSummary | null;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface RiskRow {
  id: number;
  roll_number: string;
  name: string;
  department: string;
  semester: number;
  mentor: string | null;
  current_percentage: number | null;
  projected_percentage: number | null;
  trend: Trend;
  risk_level: RiskLevel;
  reason: string;
  recommended_action: string;
  classes_required: number | null;
  recovery_possible: boolean | null;
}

export interface ImportSummary {
  id: number;
  filename: string;
  file_type: string;
  mode: string;
  status: "COMPLETED" | "REJECTED";
  rows_total: number;
  rows_inserted: number;
  rows_updated: number;
  rows_rejected: number;
  uploaded_by: string | null;
  created_at: string;
}

export interface Summary {
  target_percentage: number;
  total_students: number;
  students_with_data: number;
  average_percentage: number | null;
  shortage_count: number;
  risk_distribution: Record<RiskLevel, number>;
  attendance_histogram: { bucket: string; count: number }[];
  departments: {
    department: Department;
    students: number;
    average_percentage: number | null;
    shortage_count: number;
    risk_distribution: Record<RiskLevel, number>;
  }[];
  subjects: {
    subject: { id: number; code: string; name: string; department: string };
    students: number;
    average_percentage: number | null;
    below_target: number;
    critical: number;
    warning: number;
  }[];
  at_risk_students: RiskRow[];
  at_risk_total: number;
  pending_condonations: number;
}

export interface Overview extends Summary {
  scope: { role: Role; label: string };
  recent_imports?: ImportSummary[];
}

export interface ShortageRow extends RiskRow {
  overall_below_target: boolean;
  subjects_below_target: {
    code: string;
    name: string;
    current_percentage: number | null;
    projected_percentage: number | null;
    risk_level: RiskLevel;
  }[];
  latest_condonation_status: CondonationStatus | null;
}

export interface DepartmentReport extends Summary {
  department: Department;
  shortage_students: ShortageRow[];
  generated_at: string;
}

export interface Alert {
  id: number;
  student_id: number | null;
  kind: "RISK" | "CONDONATION";
  severity: "INFO" | "WARNING" | "CRITICAL";
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface CondonationRequest {
  id: number;
  student: { id: number; roll_number: string; name: string; department: string; mentor: string | null };
  subject: { id: number; code: string; name: string } | null;
  reason: string;
  status: CondonationStatus;
  attendance_at_request: number | null;
  current_risk_level: RiskLevel | null;
  reviewed_by: { id: number; name: string; role: Role } | null;
  review_comment: string | null;
  created_at: string;
  reviewed_at: string | null;
  history: {
    from_status: CondonationStatus | null;
    to_status: CondonationStatus;
    actor: string | null;
    actor_role: Role | null;
    comment: string | null;
    at: string;
  }[];
}

export interface UploadIssue {
  row: number | null;
  column: string | null;
  value: string | null;
  message: string;
}

export interface UploadResult {
  success: boolean;
  dry_run: boolean;
  import_id: number | null;
  filename: string;
  file_type: string;
  mode: string;
  rows_total: number;
  rows_processed: number;
  rows_rejected: number;
  rows_inserted: number;
  rows_updated: number;
  students_affected: number;
  subjects_affected: number;
  created_students: string[];
  created_subjects: string[];
  date_range: string[];
  errors_total: number;
  errors: UploadIssue[];
  warnings: UploadIssue[];
  risk_changes: { student_id: number; roll_number: string; name: string; previous: RiskLevel | null; current: RiskLevel }[];
}

export interface RecoveryCalc extends Recovery {
  attended: number;
  conducted: number;
  target_percentage: number;
  current_percentage: number | null;
}

export interface DemoAccounts {
  enabled: boolean;
  password?: string;
  accounts: { role: Role; email: string; label: string }[];
}
