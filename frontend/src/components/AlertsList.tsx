import { useAlerts, useMarkAlertRead, useMarkAllAlertsRead } from "../api/hooks";
import { EmptyState, ErrorState, Loading, fmtDateTime } from "./ui";

const DOT: Record<string, string> = { CRITICAL: "var(--crit)", WARNING: "var(--warn-strong)", INFO: "var(--info)" };

export function AlertsList({ limit, title = "Alerts" }: { limit?: number; title?: string }) {
  const alerts = useAlerts();
  const markRead = useMarkAlertRead();
  const markAll = useMarkAllAlertsRead();
  const items = alerts.data?.items ?? [];
  const shown = limit ? items.slice(0, limit) : items;

  return (
    <section className="card" aria-labelledby="alerts-heading">
      <div className="card-head">
        <h2 id="alerts-heading">
          {title}
          {alerts.data && alerts.data.unread_count > 0 && (
            <span className="badge status-PENDING" style={{ marginLeft: 8 }}>
              {alerts.data.unread_count} unread
            </span>
          )}
        </h2>
        {alerts.data && alerts.data.unread_count > 0 && (
          <button className="btn btn-sm" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
            Mark all read
          </button>
        )}
      </div>
      {alerts.isPending ? (
        <Loading />
      ) : alerts.isError ? (
        <ErrorState error={alerts.error} onRetry={() => alerts.refetch()} />
      ) : shown.length === 0 ? (
        <EmptyState title="No alerts">You will be notified here when attendance risk changes.</EmptyState>
      ) : (
        <ul className="list">
          {shown.map((a) => (
            <li key={a.id} className={`alert-item${a.is_read ? " read" : ""}`}>
              <span className="alert-dot" style={{ background: DOT[a.severity] }} aria-hidden="true" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="small muted">
                  {a.severity} · {a.kind === "RISK" ? "Attendance risk" : "Condonation"} · {fmtDateTime(a.created_at)}
                </div>
                <div>{a.message}</div>
              </div>
              {!a.is_read && (
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => markRead.mutate(a.id)}
                  aria-label="Mark alert as read"
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
