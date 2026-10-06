import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";
import { useDepartmentReport, useDepartments } from "../api/hooks";
import {
  EmptyState,
  ErrorState,
  Histogram,
  Loading,
  RiskBadge,
  RiskDistribution,
  Stat,
  StatusBadge,
  TrendIndicator,
  fmtDateTime,
  pct,
} from "../components/ui";

export function ReportsPage() {
  const departments = useDepartments();
  const [deptId, setDeptId] = useState<number | null>(null);
  useEffect(() => {
    if (deptId === null && departments.data?.items.length) setDeptId(departments.data.items[0].id);
  }, [departments.data, deptId]);
  const report = useDepartmentReport(deptId);
  const r = report.data;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Department reports</h1>
          <p className="sub">Shortage and risk reporting for exam eligibility review and intervention planning.</p>
        </div>
        <div className="row no-print">
          <div className="field" style={{ minWidth: 240 }}>
            <label htmlFor="report-dept">Department</label>
            <select
              id="report-dept"
              value={deptId ?? ""}
              onChange={(e) => setDeptId(Number(e.target.value))}
              disabled={!departments.data}
            >
              {departments.data?.items.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} – {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {departments.isError ? (
        <div className="card">
          <ErrorState error={departments.error} onRetry={() => departments.refetch()} />
        </div>
      ) : departments.data?.items.length === 0 ? (
        <div className="card">
          <EmptyState title="No departments in your scope" />
        </div>
      ) : report.isPending ? (
        <div className="card">
          <Loading label="Building report…" />
        </div>
      ) : report.isError ? (
        <div className="card">
          <ErrorState error={report.error} onRetry={() => report.refetch()} />
        </div>
      ) : r ? (
        <>
          <div className="spread">
            <h2>
              {r.department.name} ({r.department.code})
            </h2>
            <div className="row no-print">
              <a className="btn btn-primary" href={`${API_BASE}/reports/department/${r.department.id}/export.csv`} download>
                Export shortage list (CSV)
              </a>
              <button className="btn" onClick={() => window.print()}>
                Print
              </button>
            </div>
          </div>
          <p className="small muted">Generated {fmtDateTime(r.generated_at)} · target {r.target_percentage}%</p>
          <div className="grid grid-stats">
            <Stat label="Total students" value={r.total_students} />
            <Stat label="Shortage now" value={r.shortage_count} tone="crit" foot={`overall below ${r.target_percentage}%`} />
            <Stat label="Critical" value={r.risk_distribution.CRITICAL} tone="crit" />
            <Stat label="Warning" value={r.risk_distribution.WARNING} tone="warn" />
            <Stat label="Average attendance" value={pct(r.average_percentage)} />
            <Stat label="Pending condonation" value={r.pending_condonations} />
          </div>
          <div className="grid grid-2">
            <section className="card">
              <div className="card-head">
                <h2>Risk distribution</h2>
              </div>
              <RiskDistribution counts={r.risk_distribution} />
            </section>
            <section className="card">
              <div className="card-head">
                <h2>Attendance bands</h2>
              </div>
              <Histogram data={r.attendance_histogram} target={r.target_percentage} />
            </section>
          </div>
          <section className="card">
            <div className="card-head">
              <h2>Subject pattern</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th className="num">Students</th>
                    <th className="num">Average</th>
                    <th className="num">Below target</th>
                    <th className="num">Critical</th>
                    <th className="num">Warning</th>
                  </tr>
                </thead>
                <tbody>
                  {r.subjects.map((s) => (
                    <tr key={s.subject.id}>
                      <td>
                        <strong>{s.subject.name}</strong> <span className="mono small muted">{s.subject.code}</span>
                      </td>
                      <td className="num">{s.students}</td>
                      <td className="num">{pct(s.average_percentage)}</td>
                      <td className="num">{s.below_target}</td>
                      <td className="num">{s.critical}</td>
                      <td className="num">{s.warning}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="card">
            <div className="card-head">
              <h2>Shortage list</h2>
              <span className="hint">Below {r.target_percentage}% overall or in at least one subject</span>
            </div>
            {r.shortage_students.length === 0 ? (
              <EmptyState title="No shortages">Every student meets the target overall and in every subject.</EmptyState>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Student</th>
                      <th className="num">Overall</th>
                      <th className="num">Projected</th>
                      <th>Trend</th>
                      <th>Risk</th>
                      <th>Subjects below target</th>
                      <th>Condonation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.shortage_students.map((s) => (
                      <tr key={s.id}>
                        <td>
                          <Link to={`/students/${s.id}`}>
                            <strong>{s.name}</strong>
                          </Link>
                          <div className="small muted mono">{s.roll_number}</div>
                        </td>
                        <td className="num">{pct(s.current_percentage)}</td>
                        <td className="num">{pct(s.projected_percentage)}</td>
                        <td>
                          <TrendIndicator trend={s.trend} />
                        </td>
                        <td>
                          <RiskBadge level={s.risk_level} />
                        </td>
                        <td className="small">
                          {s.subjects_below_target.length
                            ? s.subjects_below_target.map((x) => `${x.code} ${pct(x.current_percentage)}`).join(", ")
                            : "—"}
                        </td>
                        <td>{s.latest_condonation_status ? <StatusBadge status={s.latest_condonation_status} /> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="small muted" style={{ marginTop: 10 }}>
              This report lists attendance below the configured threshold. It is not an examination-eligibility ruling;
              apply the institution&apos;s official rules and approved condonations.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
