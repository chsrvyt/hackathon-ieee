import { Link, useNavigate } from "react-router-dom";
import { useOverview } from "../api/hooks";
import type { RiskRow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AlertsList } from "../components/AlertsList";
import {
  EmptyState,
  ErrorState,
  Histogram,
  Loading,
  RiskBadge,
  RiskDistribution,
  Stat,
  TrendIndicator,
  fmtDateTime,
  pct, TableWrap } from "../components/ui";

export function RiskTable({ rows, compact }: { rows: RiskRow[]; compact?: boolean }) {
  const navigate = useNavigate();
  if (rows.length === 0) return <EmptyState title="No students at risk">Everyone in scope is on track.</EmptyState>;
  return (
    <TableWrap label="At-risk students">
      <table>
        <thead>
          <tr>
            <th>Student</th>
            {!compact && <th>Dept</th>}
            <th className="num">Current</th>
            <th className="num">Projected</th>
            <th>Trend</th>
            <th>Risk</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="clickable" onClick={() => navigate(`/students/${r.id}`)}>
              <td className="cell-title">
                <Link to={`/students/${r.id}`} onClick={(e) => e.stopPropagation()}>
                  <strong>{r.name}</strong>
                </Link>
                <div className="small muted mono">
                  {r.roll_number}
                  <span className="cards-only"> · {r.department}</span>
                </div>
              </td>
              {!compact && <td className="hide-cards">{r.department}</td>}
              <td className="num cell-num" data-label="Current">
                {pct(r.current_percentage)}
              </td>
              <td className="num cell-num" data-label="Projected">
                {pct(r.projected_percentage)}
              </td>
              <td className="cell-num" data-label="Trend">
                <TrendIndicator trend={r.trend} />
              </td>
              <td className="cell-badge">
                <RiskBadge level={r.risk_level} />
              </td>
              <td className="reason-cell small cell-wide">{r.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const overview = useOverview();
  if (!user) return null;

  if (overview.isPending)
    return (
      <div className="page">
        <div className="card">
          <Loading label="Loading dashboard…" />
        </div>
      </div>
    );
  if (overview.isError)
    return (
      <div className="page">
        <div className="card">
          <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
        </div>
      </div>
    );

  const o = overview.data;
  const d = o.risk_distribution;
  const isMentor = user.role === "MENTOR";
  const title =
    user.role === "MENTOR" ? "Mentor dashboard" : user.role === "EXAM_CELL" ? "Exam Cell overview" : "Admin dashboard";

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          <p className="sub">
            Scope: {o.scope.label} · target {o.target_percentage}% attendance
          </p>
        </div>
        <div className="row no-print desktop-only">
          {user.role === "ADMIN" && (
            <Link className="btn btn-primary" to="/upload">
              Upload attendance
            </Link>
          )}
          {(user.role === "ADMIN" || user.role === "EXAM_CELL") && (
            <Link className="btn" to="/reports">
              Department reports
            </Link>
          )}
        </div>
      </div>

      {o.total_students === 0 ? (
        <div className="card">
          <EmptyState title="No students in your scope yet">
            {user.role === "ADMIN" ? "Import attendance to get started." : "Ask the administrator to assign students."}
          </EmptyState>
        </div>
      ) : (
        <>
          <div className="grid grid-stats">
            <Stat label={isMentor ? "My students" : "Students"} value={o.total_students} foot={`${o.students_with_data} with attendance data`} />
            <Stat label="Critical" value={d.CRITICAL} tone="crit" foot="projected below target" />
            <Stat label="Warning" value={d.WARNING} tone="warn" foot="near target or declining" />
            <Stat label="Safe" value={d.SAFE} tone="safe" foot="on track" />
            <Stat label="Shortage now" value={o.shortage_count} foot={`currently below ${o.target_percentage}%`} />
            <Stat label="Average attendance" value={pct(o.average_percentage)} foot="all recorded classes" />
          </div>

          <div className="grid grid-2">
            <section className="card" aria-labelledby="dist-heading">
              <div className="card-head">
                <h2 id="dist-heading">Risk distribution</h2>
                <span className="hint">{o.total_students} students</span>
              </div>
              <RiskDistribution counts={d} />
              {o.pending_condonations > 0 && (
                <p className="notice notice-info small" style={{ marginTop: 14 }}>
                  {o.pending_condonations} condonation request{o.pending_condonations === 1 ? "" : "s"} pending.{" "}
                  <Link to="/condonation">Review now</Link>
                </p>
              )}
            </section>
            <section className="card" aria-labelledby="hist-heading">
              <div className="card-head">
                <h2 id="hist-heading">Current attendance distribution</h2>
                <span className="hint">students per band</span>
              </div>
              <Histogram data={o.attendance_histogram} target={o.target_percentage} />
            </section>
          </div>

          <section className="card" aria-labelledby="risk-heading">
            <div className="card-head">
              <h2 id="risk-heading">{isMentor ? "Students needing attention" : "Highest-risk students"}</h2>
              <Link className="small" to="/students?risk=CRITICAL,WARNING">
                View all {o.at_risk_total} at-risk students →
              </Link>
            </div>
            <RiskTable rows={o.at_risk_students} compact={isMentor} />
          </section>

          <div className="grid grid-2">
            {!isMentor && o.departments.length > 0 && (
              <section className="card" aria-labelledby="dept-heading">
                <div className="card-head">
                  <h2 id="dept-heading">Departments</h2>
                </div>
                <TableWrap label="Departments">
                  <table>
                    <thead>
                      <tr>
                        <th>Department</th>
                        <th className="num">Students</th>
                        <th className="num">Average</th>
                        <th className="num">Shortage</th>
                        <th className="num">Critical</th>
                      </tr>
                    </thead>
                    <tbody>
                      {o.departments.map((dep) => (
                        <tr key={dep.department.id}>
                          <td className="cell-title">
                            <strong>{dep.department.code}</strong>
                            <div className="small muted">{dep.department.name}</div>
                          </td>
                          <td className="num cell-num" data-label="Students">{dep.students}</td>
                          <td className="num cell-num" data-label="Average">{pct(dep.average_percentage)}</td>
                          <td className="num cell-num" data-label="Shortage">{dep.shortage_count}</td>
                          <td className="num cell-num" data-label="Critical">{dep.risk_distribution.CRITICAL}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              </section>
            )}
            <section className="card" aria-labelledby="subj-heading">
              <div className="card-head">
                <h2 id="subj-heading">Subject patterns</h2>
                <span className="hint">where shortages concentrate</span>
              </div>
              <TableWrap label="Subject patterns">
                <table>
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th className="num">Average</th>
                      <th className="num">Below target</th>
                      <th className="num">Critical</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.subjects.map((s) => (
                      <tr key={s.subject.id}>
                        <td className="cell-title">
                          <strong>{s.subject.name}</strong>
                          <div className="small muted mono">
                            {s.subject.code} · {s.subject.department}
                          </div>
                        </td>
                        <td className="num cell-num" data-label="Average">{pct(s.average_percentage)}</td>
                        <td className="num cell-num" data-label="Below target">
                          {s.below_target}/{s.students}
                        </td>
                        <td className="num cell-num" data-label="Critical">{s.critical}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </section>
            {isMentor && <AlertsList limit={6} title="Mentor alerts" />}
          </div>

          {o.recent_imports && o.recent_imports.length > 0 && (
            <section className="card" aria-labelledby="imports-heading">
              <div className="card-head">
                <h2 id="imports-heading">Recent imports</h2>
                <Link className="small" to="/upload">
                  Upload new file →
                </Link>
              </div>
              <TableWrap label="Recent imports">
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Status</th>
                      <th className="num">Rows</th>
                      <th>By</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.recent_imports.map((i) => (
                      <tr key={i.id}>
                        <td className="mono small cell-title">{i.filename}</td>
                        <td className="cell-badge">
                          <span className={`badge ${i.status === "COMPLETED" ? "risk-SAFE" : "risk-CRITICAL"}`}>
                            {i.status}
                          </span>
                        </td>
                        <td className="num cell-num" data-label="Rows">
                          {i.status === "COMPLETED"
                            ? `${i.rows_inserted} new, ${i.rows_updated} updated`
                            : `${i.rows_rejected} rejected`}
                        </td>
                        <td className="cell-num" data-label="By">{i.uploaded_by ?? "—"}</td>
                        <td className="small cell-num" data-label="When">{fmtDateTime(i.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </section>
          )}
        </>
      )}
    </div>
  );
}
