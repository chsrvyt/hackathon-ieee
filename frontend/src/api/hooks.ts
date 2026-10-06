import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type {
  Alert,
  CondonationRequest,
  CondonationStatus,
  Department,
  DepartmentReport,
  DemoAccounts,
  ImportSummary,
  Overview,
  Paged,
  RecoveryCalc,
  StudentAnalytics,
  StudentSummary,
  UploadResult,
} from "./types";

export const keys = {
  me: ["me"] as const,
  overview: ["overview"] as const,
  students: (params: string) => ["students", params] as const,
  student: (id: number) => ["student", id] as const,
  analytics: (id: number) => ["analytics", id] as const,
  alerts: ["alerts"] as const,
  condonations: (status: string) => ["condonations", status] as const,
  studentCondonations: (id: number) => ["condonations", "student", id] as const,
  departments: ["departments"] as const,
  department: (id: number) => ["department", id] as const,
  imports: ["imports"] as const,
  demo: ["demo-accounts"] as const,
};

export function useDemoAccounts(enabled = true) {
  return useQuery({
    queryKey: keys.demo,
    queryFn: () => api<DemoAccounts>("/auth/demo-accounts", { silent401: true }),
    staleTime: Infinity,
    retry: false,
    enabled,
  });
}

export function useOverview(enabled = true) {
  return useQuery({ queryKey: keys.overview, queryFn: () => api<Overview>("/analytics/overview"), enabled });
}

export function useStudents(params: URLSearchParams) {
  const qs = params.toString();
  return useQuery({
    queryKey: keys.students(qs),
    queryFn: () => api<Paged<StudentSummary>>(`/students?${qs}`),
    placeholderData: (prev) => prev,
  });
}

export function useStudentAnalytics(id: number | null | undefined) {
  return useQuery({
    queryKey: keys.analytics(id ?? 0),
    queryFn: () => api<StudentAnalytics>(`/analytics/student/${id}`),
    enabled: !!id,
  });
}

export function useAlerts() {
  return useQuery({
    queryKey: keys.alerts,
    queryFn: () => api<{ items: Alert[]; unread_count: number }>("/alerts"),
    refetchInterval: 60_000,
  });
}

export function useMarkAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api(`/alerts/${id}/read`, { method: "PATCH" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.alerts }),
  });
}

export function useMarkAllAlertsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/alerts/read-all", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.alerts }),
  });
}

export function useCondonations(status: CondonationStatus | "ALL", enabled = true) {
  return useQuery({
    queryKey: keys.condonations(status),
    queryFn: () => api<{ items: CondonationRequest[]; can_review: boolean }>(`/condonation?status=${status}`),
    enabled,
  });
}

export function useStudentCondonations(studentId: number | null | undefined) {
  return useQuery({
    queryKey: keys.studentCondonations(studentId ?? 0),
    queryFn: () => api<{ items: CondonationRequest[] }>(`/condonation/student/${studentId}`),
    enabled: !!studentId,
  });
}

export function useSubmitCondonation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { reason: string; subject_id: number | null }) =>
      api<{ request: CondonationRequest }>("/condonation", { json: body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["condonations"] });
      qc.invalidateQueries({ queryKey: keys.alerts });
    },
  });
}

export function useWithdrawCondonation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<{ request: CondonationRequest }>(`/condonation/${id}/withdraw`, { method: "PATCH" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["condonations"] }),
  });
}

export function useDecideCondonation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, comment }: { id: number; decision: "APPROVED" | "REJECTED"; comment: string }) =>
      api<{ request: CondonationRequest }>(`/condonation/${id}/decision`, {
        method: "PATCH",
        json: { decision, comment: comment || null },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["condonations"] });
      qc.invalidateQueries({ queryKey: keys.overview });
    },
  });
}

export function useDepartments() {
  return useQuery({
    queryKey: keys.departments,
    queryFn: () => api<{ items: Department[] }>("/departments"),
    staleTime: 5 * 60_000,
  });
}

export function useDepartmentReport(id: number | null) {
  return useQuery({
    queryKey: keys.department(id ?? 0),
    queryFn: () => api<DepartmentReport>(`/analytics/department/${id}`),
    enabled: !!id,
  });
}

export function useImports(enabled = true) {
  return useQuery({
    queryKey: keys.imports,
    queryFn: () => api<{ items: ImportSummary[] }>("/attendance/imports"),
    enabled,
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (form: FormData) => api<UploadResult>("/attendance/upload", { form }),
    onSettled: (data) => {
      qc.invalidateQueries({ queryKey: keys.imports });
      if (data && !data.dry_run) {
        // Imported data changes every analytics view.
        qc.invalidateQueries({ queryKey: keys.overview });
        qc.invalidateQueries({ queryKey: ["students"] });
        qc.invalidateQueries({ queryKey: ["analytics"] });
        qc.invalidateQueries({ queryKey: ["department"] });
        qc.invalidateQueries({ queryKey: keys.alerts });
      }
    },
  });
}

export function useRecoveryCalc(params: { attended: number; conducted: number; target: number; remaining: number } | null) {
  const qs = params
    ? new URLSearchParams({
        attended: String(params.attended),
        conducted: String(params.conducted),
        target: String(params.target),
        remaining: String(params.remaining),
      }).toString()
    : "";
  return useQuery({
    queryKey: ["recovery", qs],
    queryFn: () => api<RecoveryCalc>(`/analytics/recovery?${qs}`),
    enabled: !!params,
    placeholderData: (prev) => prev,
    retry: false,
  });
}
