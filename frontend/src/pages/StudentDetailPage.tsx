import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { useStudentAnalytics, useStudentCondonations } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { CondonationCard } from "../components/Condonation";
import { StudentAnalyticsView } from "../components/StudentAnalyticsView";
import { EmptyState, ErrorState, Loading } from "../components/ui";

export function StudentDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const studentId = Number(id);
  const valid = Number.isInteger(studentId) && studentId > 0;
  const analytics = useStudentAnalytics(valid ? studentId : null);
  const requests = useStudentCondonations(valid ? studentId : null);
  const canReview = user?.role === "MENTOR" || user?.role === "ADMIN";

  if (!valid) return <EmptyState title="Invalid student id" />;

  const forbidden = analytics.error instanceof ApiError && analytics.error.status === 403;
  const missing = analytics.error instanceof ApiError && analytics.error.status === 404;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to="/students" className="small">
            ← Students
          </Link>
          <h1 style={{ marginTop: 6 }}>{analytics.data ? analytics.data.student.name : "Student"}</h1>
          {analytics.data && (
            <p className="sub">
              <span className="mono">{analytics.data.student.roll_number}</span> ·{" "}
              {analytics.data.student.department.name} · Semester {analytics.data.student.semester} · Mentor:{" "}
              {analytics.data.student.mentor?.name ?? "not assigned"}
            </p>
          )}
        </div>
        <button className="btn no-print" onClick={() => window.print()}>
          Print summary
        </button>
      </div>

      {analytics.isPending ? (
        <div className="card">
          <Loading label="Calculating analytics…" />
        </div>
      ) : forbidden || missing ? (
        <div className="card">
          <EmptyState title={forbidden ? "Access denied" : "Student not found"}>
            {forbidden ? "This student is outside your authorised scope." : "No student with this id exists."}
          </EmptyState>
        </div>
      ) : analytics.isError ? (
        <div className="card">
          <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />
        </div>
      ) : (
        <>
          <StudentAnalyticsView data={analytics.data} audience="staff" />
          <section className="card" aria-labelledby="student-condonation">
            <div className="card-head">
              <h2 id="student-condonation">Condonation requests</h2>
            </div>
            {requests.isPending ? (
              <Loading />
            ) : requests.isError ? (
              <ErrorState error={requests.error} onRetry={() => requests.refetch()} />
            ) : requests.data.items.length === 0 ? (
              <p className="small muted">No condonation requests from this student.</p>
            ) : (
              <div className="stack">
                {requests.data.items.map((r) => (
                  <CondonationCard key={r.id} req={r} canReview={canReview} />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
