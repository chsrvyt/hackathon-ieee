import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { API_BASE, ApiError, errorMessage } from "../api/client";
import { useImports, useUpload } from "../api/hooks";
import type { UploadResult } from "../api/types";
import { RiskBadge, fmtDateTime } from "../components/ui";

const MAX_MB = 5;
const REQUIRED = ["student_roll", "subject_code", "date", "classes_conducted", "classes_attended"];
const OPTIONAL = ["student_name", "department", "semester", "subject_name"];

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"strict" | "replace">("strict");
  const [registerNew, setRegisterNew] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [drag, setDrag] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const upload = useUpload();
  const imports = useImports();

  const choose = (f: File | null | undefined) => {
    upload.reset();
    setLocalError(null);
    if (!f) return;
    const ext = f.name.toLowerCase().split(".").pop();
    if (ext !== "csv" && ext !== "xlsx") {
      setLocalError("Only .csv and .xlsx files are accepted.");
      setFile(null);
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setLocalError(`The file is larger than ${MAX_MB} MB.`);
      setFile(null);
      return;
    }
    setFile(f);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    choose(e.dataTransfer.files?.[0]);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    form.append("register_new", String(registerNew));
    form.append("dry_run", String(dryRun));
    upload.mutate(form);
  };

  const rejected: UploadResult | null =
    upload.error instanceof ApiError && upload.error.body && typeof upload.error.body === "object" && "rows_total" in upload.error.body
      ? (upload.error.body as UploadResult)
      : null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Upload attendance</h1>
          <p className="sub">
            The whole file is validated first. If any row is invalid, nothing is saved and every problem is listed.
          </p>
        </div>
        <a className="btn" href={`${API_BASE}/attendance/template.csv`} download>
          Download CSV template
        </a>
      </div>

      <div className="grid grid-2">
        <form className="card stack" onSubmit={submit} aria-label="Attendance upload">
          <div
            className={`dropzone${drag ? " drag" : ""}`}
            role="button"
            tabIndex={0}
            aria-describedby="file-help"
            onClick={() => input.current?.click()}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
          >
            <strong>{file ? file.name : "Choose a CSV or XLSX file"}</strong>
            <div className="small muted" id="file-help">
              {file ? `${(file.size / 1024).toFixed(1)} KB · click to change` : `Drag and drop, or click to browse · max ${MAX_MB} MB`}
            </div>
            <input
              ref={input}
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="sr-only"
              aria-label="Attendance file"
              data-testid="file-input"
              onChange={(e) => choose(e.target.files?.[0])}
            />
          </div>

          <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0, gap: 8 }}>
            <legend className="small" style={{ fontWeight: 700, marginBottom: 6 }}>
              Options
            </legend>
            <label className="check">
              <input type="checkbox" checked={mode === "replace"} onChange={(e) => setMode(e.target.checked ? "replace" : "strict")} />
              <span>
                Replace existing records
                <span className="help" style={{ display: "block" }}>
                  Overwrite rows that already exist for the same student, subject and date (otherwise they are rejected as duplicates).
                </span>
              </span>
            </label>
            <label className="check">
              <input type="checkbox" checked={registerNew} onChange={(e) => setRegisterNew(e.target.checked)} />
              <span>
                Register new students and subjects
                <span className="help" style={{ display: "block" }}>
                  Unknown roll numbers / subject codes are created from the name, department and semester columns.
                </span>
              </span>
            </label>
            <label className="check">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              <span>
                Validate only (do not save)
              </span>
            </label>
          </fieldset>

          {localError && <p className="notice notice-error small">{localError}</p>}
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={!file || upload.isPending}>
              {upload.isPending ? "Processing…" : dryRun ? "Validate file" : "Upload and process"}
            </button>
            {file && !upload.isPending && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  setFile(null);
                  upload.reset();
                  if (input.current) input.current.value = "";
                }}
              >
                Clear
              </button>
            )}
          </div>
        </form>

        <section className="card stack" aria-labelledby="format-heading">
          <h2 id="format-heading">File format</h2>
          <p className="small">
            One row per student, subject and reporting period. <code>date</code> is the end of the period
            (YYYY-MM-DD); counts are the classes conducted and attended in that period.
          </p>
          <div className="small">
            <strong>Required</strong>
            <div className="code-list">
              {REQUIRED.map((c) => (
                <code key={c}>{c}</code>
              ))}
            </div>
          </div>
          <div className="small">
            <strong>Optional (cross-checked)</strong>
            <div className="code-list">
              {OPTIONAL.map((c) => (
                <code key={c}>{c}</code>
              ))}
            </div>
          </div>
          <ul className="timeline-mini">
            <li>Rejected: attended &gt; conducted, negative or non-numeric counts, zero conducted classes</li>
            <li>Rejected: invalid or future dates, duplicate rows, unknown students/subjects</li>
            <li>Rejected: department mismatch or rows outside your department scope</li>
          </ul>
        </section>
      </div>

      <div aria-live="polite">
        {upload.isSuccess && <ResultPanel result={upload.data} />}
        {upload.isError && (
          <section className="card stack" aria-labelledby="reject-heading">
            <div className="notice notice-error" role="alert">
              <strong id="reject-heading">Upload rejected.</strong> {errorMessage(upload.error)}
            </div>
            {rejected && rejected.errors.length > 0 && (
              <>
                <p className="small muted">
                  {rejected.rows_rejected} of {rejected.rows_total} rows have problems
                  {rejected.errors_total > rejected.errors.length && ` (showing first ${rejected.errors.length} of ${rejected.errors_total})`}.
                  Fix them and upload again.
                </p>
                <IssueTable issues={rejected.errors} />
              </>
            )}
          </section>
        )}
      </div>

      <section className="card" aria-labelledby="history-heading">
        <div className="card-head">
          <h2 id="history-heading">Import history</h2>
        </div>
        {imports.data && imports.data.items.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>File</th>
                  <th>Status</th>
                  <th className="num">Rows</th>
                  <th>Mode</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {imports.data.items.map((i) => (
                  <tr key={i.id}>
                    <td className="small">{fmtDateTime(i.created_at)}</td>
                    <td className="mono small">{i.filename}</td>
                    <td>
                      <span className={`badge ${i.status === "COMPLETED" ? "risk-SAFE" : "risk-CRITICAL"}`}>{i.status}</span>
                    </td>
                    <td className="num">
                      {i.status === "COMPLETED" ? `${i.rows_inserted} new · ${i.rows_updated} updated` : `${i.rows_rejected} rejected`}
                    </td>
                    <td>{i.mode}</td>
                    <td>{i.uploaded_by ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="small muted">{imports.isPending ? "Loading…" : "No imports yet."}</p>
        )}
      </section>
    </div>
  );
}

function IssueTable({ issues }: { issues: UploadResult["errors"] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="num">Row</th>
            <th>Column</th>
            <th>Value</th>
            <th>Problem</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((e, i) => (
            <tr key={i}>
              <td className="num">{e.row ?? "—"}</td>
              <td className="mono small">{e.column ?? "—"}</td>
              <td className="mono small">{e.value ?? "—"}</td>
              <td>{e.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultPanel({ result }: { result: UploadResult }) {
  return (
    <section className="card stack" aria-labelledby="result-heading">
      <div className="notice notice-success" role="status">
        <strong id="result-heading">{result.dry_run ? "Validation passed – nothing was saved." : "Import successful."}</strong>{" "}
        {result.rows_processed} rows processed ({result.rows_inserted} new, {result.rows_updated} updated) for{" "}
        {result.students_affected} students and {result.subjects_affected} subjects
        {result.date_range.length === 2 && ` · period ${result.date_range[0]} to ${result.date_range[1]}`}.
      </div>
      <div className="grid grid-stats">
        <div className="stat">
          <div className="stat-label">Rows processed</div>
          <div className="stat-value">{result.rows_processed}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Rows rejected</div>
          <div className="stat-value">{result.rows_rejected}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Students</div>
          <div className="stat-value">{result.students_affected}</div>
        </div>
        <div className="stat">
          <div className="stat-label">Risk changes</div>
          <div className="stat-value">{result.risk_changes.length}</div>
        </div>
      </div>
      {(result.created_students.length > 0 || result.created_subjects.length > 0) && (
        <p className="small">
          Registered: {result.created_students.length} new student(s) {result.created_students.join(", ")}
          {result.created_subjects.length > 0 && `; ${result.created_subjects.length} new subject(s) ${result.created_subjects.join(", ")}`}
        </p>
      )}
      {result.risk_changes.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 8 }}>Risk level changes from this import</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Before</th>
                  <th>After</th>
                </tr>
              </thead>
              <tbody>
                {result.risk_changes.map((c) => (
                  <tr key={c.student_id}>
                    <td>
                      <Link to={`/students/${c.student_id}`}>
                        <strong>{c.name}</strong>
                      </Link>{" "}
                      <span className="mono small muted">{c.roll_number}</span>
                    </td>
                    <td>{c.previous ? <RiskBadge level={c.previous} /> : <span className="muted">new</span>}</td>
                    <td>
                      <RiskBadge level={c.current} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {result.warnings.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 8 }}>Warnings (not blocking)</h3>
          <IssueTable issues={result.warnings} />
        </div>
      )}
      <div className="row">
        <Link className="btn btn-primary" to="/dashboard">
          Open dashboard
        </Link>
        <Link className="btn" to="/students?risk=CRITICAL">
          View critical students
        </Link>
      </div>
    </section>
  );
}
