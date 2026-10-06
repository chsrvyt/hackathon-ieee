import { useStudentAnalytics, useStudentCondonations } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { CondonationCard, CondonationForm } from "../components/Condonation";
import { EmptyState, ErrorState, Loading } from "../components/ui";

/** Student view of the condonation workflow: submit a request and follow its status. */
export function StudentRequestsPage() {
  const { user } = useAuth();
  const studentId = user?.student_id;
  const analytics = useStudentAnalytics(studentId);
  const requests = useStudentCondonations(studentId);

  if (!studentId) {
    return (
      <div className="page">
        <div className="card">
          <EmptyState title="No student record linked">Please contact the administrator.</EmptyState>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Condonation requests</h1>
          <p className="sub">
            If absences had a valid reason (for example illness), ask your mentor to condone the shortage.
          </p>
        </div>
      </div>
      <div className="grid grid-2">
        <section className="card" aria-labelledby="new-request-heading">
          <div className="card-head">
            <h2 id="new-request-heading">New request</h2>
          </div>
          {analytics.isPending ? (
            <Loading />
          ) : analytics.isError ? (
            <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />
          ) : (
            <CondonationForm analytics={analytics.data} />
          )}
        </section>
        <section className="card" aria-labelledby="my-requests-heading">
          <div className="card-head">
            <h2 id="my-requests-heading">Your requests</h2>
            {requests.data && <span className="hint">{requests.data.items.length} total</span>}
          </div>
          {requests.isPending ? (
            <Loading />
          ) : requests.isError ? (
            <ErrorState error={requests.error} onRetry={() => requests.refetch()} />
          ) : requests.data.items.length === 0 ? (
            <EmptyState title="No requests yet">Submitted requests and decisions appear here.</EmptyState>
          ) : (
            <div className="stack">
              {requests.data.items.map((r) => (
                <CondonationCard key={r.id} req={r} canWithdraw />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
