import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useDepartments, useStudents } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, Loading, RiskBadge, TrendIndicator, pct } from "../components/ui";

const PAGE_SIZE = 20;

export function StudentsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("search") ?? "");
  const departments = useDepartments();

  // Debounce the free-text search into the URL.
  useEffect(() => {
    const t = setTimeout(() => {
      const next = new URLSearchParams(params);
      if (search.trim()) next.set("search", search.trim());
      else next.delete("search");
      if (next.toString() !== params.toString()) {
        next.delete("page");
        setParams(next, { replace: true });
      }
    }, 300);
    return () => clearTimeout(t);
  }, [search, params, setParams]);

  const query = new URLSearchParams(params);
  query.set("page_size", String(PAGE_SIZE));
  if (!query.get("sort")) query.set("sort", "risk");
  const students = useStudents(query);
  const page = Number(params.get("page") ?? 1);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete("page");
    setParams(next, { replace: true });
  };

  const total = students.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{user?.role === "MENTOR" ? "My students" : "Students"}</h1>
          <p className="sub">Sorted by risk by default. Select a student to see the full explanation.</p>
        </div>
      </div>
      <section className="card">
        <div className="filters" role="search">
          <div className="field">
            <label htmlFor="search">Search</label>
            <input
              id="search"
              type="search"
              placeholder="Name or roll number"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="risk">Risk</label>
            <select id="risk" value={params.get("risk") ?? ""} onChange={(e) => setParam("risk", e.target.value)}>
              <option value="">All levels</option>
              <option value="CRITICAL,WARNING">At risk (critical + warning)</option>
              <option value="CRITICAL">Critical</option>
              <option value="WARNING">Warning</option>
              <option value="SAFE">Safe</option>
              <option value="NO_DATA">No data</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="dept">Department</label>
            <select
              id="dept"
              value={params.get("department_id") ?? ""}
              onChange={(e) => setParam("department_id", e.target.value)}
            >
              <option value="">All in scope</option>
              {departments.data?.items.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} – {d.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sort">Sort by</label>
            <select id="sort" value={params.get("sort") ?? "risk"} onChange={(e) => setParam("sort", e.target.value)}>
              <option value="risk">Risk (highest first)</option>
              <option value="projected">Projected % (lowest first)</option>
              <option value="current">Current % (lowest first)</option>
              <option value="roll">Roll number</option>
              <option value="name">Name</option>
            </select>
          </div>
        </div>
      </section>

      <section className="card" aria-live="polite">
        {students.isPending ? (
          <Loading label="Loading students…" />
        ) : students.isError ? (
          <ErrorState error={students.error} onRetry={() => students.refetch()} />
        ) : students.data.items.length === 0 ? (
          <EmptyState title="No students match these filters" />
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Dept · Sem</th>
                    <th className="num">Current</th>
                    <th className="num">Projected</th>
                    <th>Trend</th>
                    <th>Risk</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {students.data.items.map((s) => (
                    <tr
                      key={s.id}
                      className="clickable"
                      tabIndex={0}
                      onClick={() => navigate(`/students/${s.id}`)}
                      onKeyDown={(e) => e.key === "Enter" && navigate(`/students/${s.id}`)}
                    >
                      <td>
                        <Link to={`/students/${s.id}`} onClick={(e) => e.stopPropagation()}>
                          <strong>{s.name}</strong>
                        </Link>
                        <div className="small muted mono">{s.roll_number}</div>
                      </td>
                      <td>
                        {s.department.code} · {s.semester}
                      </td>
                      <td className="num">{pct(s.analytics?.current_percentage)}</td>
                      <td className="num">{pct(s.analytics?.projected_percentage)}</td>
                      <td>{s.analytics ? <TrendIndicator trend={s.analytics.trend} /> : "—"}</td>
                      <td>
                        <RiskBadge level={s.analytics?.risk_level ?? "NO_DATA"} />
                      </td>
                      <td className="reason-cell small">{s.analytics?.reason ?? "No attendance recorded yet."}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <span className="small muted">
                {total} student{total === 1 ? "" : "s"} · page {page} of {pages}
              </span>
              <div className="row">
                <button
                  className="btn btn-sm"
                  disabled={page <= 1}
                  onClick={() => setParam("page", String(page - 1))}
                >
                  Previous
                </button>
                <button
                  className="btn btn-sm"
                  disabled={page >= pages}
                  onClick={() => {
                    const next = new URLSearchParams(params);
                    next.set("page", String(page + 1));
                    setParams(next, { replace: true });
                  }}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
