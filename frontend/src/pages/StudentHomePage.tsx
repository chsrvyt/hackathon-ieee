import { Link } from "react-router-dom";
import { useStudentAnalytics, useStudentCondonations } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { AlertsList } from "../components/AlertsList";
import { StudentAnalyticsView } from "../components/StudentAnalyticsView";
import { EmptyState, ErrorState, Loading, StatusBadge, fmtDateTime } from "../components/ui";

export function StudentHomePage() {
  const { user } = useAuth();
  const studentId = user?.student_id;
  const analytics = useStudentAnalytics(studentId);
  const requests = useStudentCondonations(studentId);

  if (!studentId) {
    return (
      <div className="page">
        <div className="card">
          <EmptyState title="No student record linked">
            Your account is not linked to a student record yet. Please contact the administrator.
          </EmptyState>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>My attendance</h1>
          {analytics.data && (
            <p className="sub">
              {analytics.data.student.name} · <span className="mono">{analytics.data.student.roll_number}</span> ·{" "}
              {analytics.data.student.department.name} · Semester {analytics.data.student.semester}
              {analytics.data.student.mentor && <> · Mentor: {analytics.data.student.mentor.name}</>}
            </p>
          )}
        </div>
      </div>

      {analytics.isPending ? (
        <div className="card">
          <Loading label="Calculating your attendance analytics…" />
        </div>
      ) : analytics.isError ? (
        <div className="card">
          <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />
        </div>
      ) : (
        <StudentAnalyticsView data={analytics.data} audience="student" />
      )}

      <div className="grid grid-2">
        <AlertsList limit={6} />
        <section className="card" aria-labelledby="condonation-heading">
          <div className="card-head">
            <h2 id="condonation-heading">Condonation</h2>
          </div>
          <div className="stack">
            {requests.isPending ? (
              <Loading />
            ) : requests.isError ? (
              <ErrorState error={requests.error} onRetry={() => requests.refetch()} />
            ) : requests.data.items.length === 0 ? (
              <p className="small muted">You have not submitted any condonation requests.</p>
            ) : (
              <div className="row">
                <StatusBadge status={requests.data.items[0].status} />
                <span className="small">
                  Latest request
                  {requests.data.items[0].subject ? ` (${requests.data.items[0].subject.name})` : " (overall)"} ·{" "}
                  {fmtDateTime(requests.data.items[0].created_at)}
                </span>
              </div>
            )}
            {analytics.data && (analytics.data.risk_level === "WARNING" || analytics.data.risk_level === "CRITICAL") ? (
              <p className="small">
                Your attendance is at risk. If the absences had a valid reason, you can ask your mentor to condone
                the shortage.
              </p>
            ) : (
              <p className="small muted">Requests open when your attendance is at risk (WARNING or CRITICAL).</p>
            )}
            <div>
              <Link className="btn btn-primary" to="/condonation">
                Open condonation requests
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
