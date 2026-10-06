import type { StudentAnalytics } from "../api/types";
import { RecoveryCalculator } from "./RecoveryCalculator";
import { TimelineChart } from "./TimelineChart";
import { AttendanceBar, EmptyState, RiskBadge, TrendIndicator, fmtDate, pct, TableWrap } from "./ui";

function tone(level: string) {
  return level === "CRITICAL" ? "crit" : level === "WARNING" ? "warn" : level === "SAFE" ? "safe" : "";
}

/** The explainable risk picture for one student. Shared by the student's own view and staff drill-down. */
export function StudentAnalyticsView({ data, audience }: { data: StudentAnalytics; audience: "student" | "staff" }) {
  const o = data.overall;
  if (o.classes_conducted === 0) {
    return (
      <div className="card">
        <EmptyState title="No attendance recorded yet">
          Risk and projections appear after the first attendance file that includes this student is imported.
        </EmptyState>
      </div>
    );
  }
  const you = audience === "student";
  const trendDetail = o.trend_detail;
  const recovery = data.recovery;

  return (
    <>
      <section className="card" aria-labelledby="risk-heading">
        <div className="hero">
          <div>
            <div className="spread">
              <h2 id="risk-heading">{you ? "Your attendance risk" : "Attendance risk"}</h2>
              <RiskBadge level={data.risk_level} large />
            </div>
            <div className="hero-figures">
              <div className="figure">
                <div className="k">Current</div>
                <div className={`v ${data.current_percentage! < data.target_percentage ? "crit" : ""}`}>
                  {pct(data.current_percentage)}
                </div>
                <div className="small muted">
                  {o.classes_attended}/{o.classes_conducted} classes
                </div>
              </div>
              <div className="figure">
                <div className="k">Projected</div>
                <div className={`v ${tone(o.risk_level)}`}>{pct(data.projected_percentage)}</div>
                <div className="small muted">end of term</div>
              </div>
              <div className="figure">
                <div className="k">Target</div>
                <div className="v">{pct(data.target_percentage, 0)}</div>
                <div className="small muted">minimum required</div>
              </div>
            </div>
            <AttendanceBar value={data.current_percentage} target={data.target_percentage} level={data.risk_level} />
            <p className="small muted" style={{ marginTop: 8 }}>
              Trend: <TrendIndicator trend={data.trend} />
              {trendDetail.change_points !== null && (
                <>
                  {" "}
                  — recent {pct(trendDetail.recent_percentage)} vs earlier {pct(trendDetail.previous_percentage)} (
                  {trendDetail.change_points > 0 ? "+" : ""}
                  {trendDetail.change_points.toFixed(1)} pts)
                </>
              )}
            </p>
          </div>
          <dl className={`explain ${data.risk_level}`} aria-label="Why this risk level">
            <dt>Why this rating</dt>
            <dd>{data.reason}</dd>
            <dt>Recommended next step</dt>
            <dd className="action-box">{data.recommended_action}</dd>
            <dt>How the projection works</dt>
            <dd className="small muted">
              Continues the recent rate ({pct(o.projection.rate_used_percentage)} over the last{" "}
              {trendDetail.recent_window.length || 1} reporting period
              {trendDetail.recent_window.length === 1 ? "" : "s"}) for the {o.projection.remaining_classes} remaining
              planned classes. Risk: CRITICAL if projected &lt; {data.policy.target_percentage}%, WARNING if within{" "}
              {data.policy.warning_band_points} points, currently below target, or recent attendance is falling
              towards the line.
            </dd>
          </dl>
        </div>
      </section>

      <div className="grid grid-2">
        <section className="card" aria-labelledby="recovery-heading">
          <div className="card-head">
            <h2 id="recovery-heading">Recovery plan</h2>
            <span className={`badge ${recovery.possible ? "risk-SAFE" : "risk-CRITICAL"}`}>
              {recovery.status === "ALREADY_MET"
                ? "Target met"
                : recovery.possible
                  ? "Recoverable"
                  : "Not recoverable this term"}
            </span>
          </div>
          <div className="stack">
            {recovery.status === "ALREADY_MET" ? (
              <p>
                <strong>{you ? "You are" : "Student is"} at or above the target.</strong> Buffer:{" "}
                <strong>{recovery.buffer_classes}</strong> class{recovery.buffer_classes === 1 ? "" : "es"} above the
                minimum.
              </p>
            ) : recovery.classes_required !== null ? (
              <p style={{ fontSize: "1.05rem" }}>
                Attend the next <strong style={{ fontSize: "1.4rem" }}>{recovery.classes_required}</strong> classes in a
                row to return to {data.target_percentage}%.
              </p>
            ) : null}
            {recovery.status !== "ALREADY_MET" && <p className="small">{recovery.message}</p>}
            <ul className="timeline-mini">
              <li>
                Remaining planned classes: <strong>{recovery.remaining_classes}</strong>
              </li>
              {recovery.classes_needed_of_remaining !== null && (
                <li>
                  To finish the term at {data.target_percentage}%: attend at least{" "}
                  <strong>
                    {Math.min(recovery.classes_needed_of_remaining, recovery.remaining_classes)} of{" "}
                    {recovery.remaining_classes}
                  </strong>
                  {recovery.classes_needed_of_remaining > recovery.remaining_classes && " (not enough classes left)"}
                </li>
              )}
              <li>
                Best possible end-of-term attendance: <strong>{pct(recovery.max_achievable_percentage)}</strong>
              </li>
            </ul>
            <p className="small muted">
              Formula: minimum X with (attended + X) / (conducted + X) ≥ {data.target_percentage}%.
            </p>
          </div>
        </section>
        <RecoveryCalculator
          attended={o.classes_attended}
          conducted={o.classes_conducted}
          target={data.target_percentage}
          remaining={o.projection.remaining_classes}
        />
      </div>

      <section className="card" aria-labelledby="subjects-heading">
        <div className="card-head">
          <h2 id="subjects-heading">Subject-wise attendance</h2>
          <span className="hint">Each subject must also meet the {data.target_percentage}% target</span>
        </div>
        <TableWrap label="Subject-wise attendance">
          <table>
            <thead>
              <tr>
                <th>Subject</th>
                <th className="num">Attended</th>
                <th style={{ minWidth: 140 }}>Current</th>
                <th className="num">Projected</th>
                <th>Trend</th>
                <th>Risk</th>
                <th>Next step</th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((s) => (
                <tr key={s.subject.id}>
                  <td className="cell-title">
                    <strong>{s.subject.name}</strong>
                    <div className="small muted mono">{s.subject.code}</div>
                  </td>
                  <td className="num cell-num" data-label="Attended">
                    {s.classes_attended}/{s.classes_conducted}
                  </td>
                  <td className="cell-num" data-label="Current">
                    <div className="small" style={{ fontWeight: 600 }}>
                      {pct(s.current_percentage)}
                    </div>
                    <AttendanceBar value={s.current_percentage} target={s.target_percentage} level={s.risk_level} />
                  </td>
                  <td className="num cell-num" data-label="Projected">
                    {pct(s.projected_percentage)}
                  </td>
                  <td className="cell-num" data-label="Trend">
                    <TrendIndicator trend={s.trend} />
                  </td>
                  <td className="cell-badge">
                    <RiskBadge level={s.risk_level} />
                  </td>
                  <td className="reason-cell small cell-wide" data-label="Next step">
                    {s.recovery.status === "RECOVERABLE"
                      ? `Attend next ${s.recovery.classes_required} classes`
                      : s.recovery.status === "NOT_RECOVERABLE_THIS_TERM"
                        ? "Target unreachable this term – condonation route"
                        : s.risk_level === "SAFE"
                          ? `Buffer ${s.recovery.buffer_classes} classes`
                          : "Avoid further absences"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
        <details style={{ marginTop: 12 }}>
          <summary className="small" style={{ cursor: "pointer" }}>
            Subject explanations
          </summary>
          <ul className="list small">
            {data.subjects.map((s) => (
              <li key={s.subject.id}>
                <strong>{s.subject.name}</strong> <RiskBadge level={s.risk_level} />
                <div>{s.reason}</div>
                <div className="muted">Next step: {s.recommended_action}</div>
              </li>
            ))}
          </ul>
        </details>
      </section>

      <section className="card" aria-labelledby="timeline-heading">
        <div className="card-head">
          <h2 id="timeline-heading">Attendance over time</h2>
          <span className="hint">
            {data.timeline.length} reporting period{data.timeline.length === 1 ? "" : "s"} · latest{" "}
            {fmtDate(data.timeline[data.timeline.length - 1]?.date)}
          </span>
        </div>
        <TimelineChart points={data.timeline} target={data.target_percentage} />
        <p className="small muted" style={{ marginTop: 8 }}>
          {data.disclaimer}
        </p>
      </section>
    </>
  );
}
