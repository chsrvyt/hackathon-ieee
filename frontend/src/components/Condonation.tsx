import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useDecideCondonation, useSubmitCondonation, useWithdrawCondonation } from "../api/hooks";
import type { CondonationRequest, StudentAnalytics } from "../api/types";
import { Modal, RiskBadge, StatusBadge, fmtDateTime, pct } from "./ui";

export function CondonationCard({
  req,
  showStudent,
  canReview,
  canWithdraw,
}: {
  req: CondonationRequest;
  showStudent?: boolean;
  canReview?: boolean;
  canWithdraw?: boolean;
}) {
  const [deciding, setDeciding] = useState<null | "APPROVED" | "REJECTED">(null);
  const withdraw = useWithdrawCondonation();
  return (
    <article className="card" style={{ boxShadow: "none" }} aria-label={`Condonation request ${req.id}`}>
      <div className="spread">
        <div className="row">
          <StatusBadge status={req.status} />
          <strong>{req.subject ? `${req.subject.name} (${req.subject.code})` : "Overall attendance"}</strong>
        </div>
        <span className="small muted">Submitted {fmtDateTime(req.created_at)}</span>
      </div>
      {showStudent && (
        <div className="row small" style={{ marginTop: 8 }}>
          <Link to={`/students/${req.student.id}`}>
            <strong>{req.student.name}</strong>
          </Link>
          <span className="mono muted">{req.student.roll_number}</span>
          <span className="muted">{req.student.department}</span>
          {req.current_risk_level && <RiskBadge level={req.current_risk_level} />}
        </div>
      )}
      <p style={{ marginTop: 8 }}>{req.reason}</p>
      <p className="small muted" style={{ marginTop: 6 }}>
        Attendance when submitted: {pct(req.attendance_at_request)}
      </p>
      {req.reviewed_by && (
        <p className="small" style={{ marginTop: 6 }}>
          <strong>
            {req.status === "APPROVED" ? "Approved" : "Rejected"} by {req.reviewed_by.name}
          </strong>{" "}
          on {fmtDateTime(req.reviewed_at)}
          {req.review_comment && <> — “{req.review_comment}”</>}
        </p>
      )}
      {req.history.length > 1 && (
        <details style={{ marginTop: 6 }}>
          <summary className="small" style={{ cursor: "pointer" }}>
            History
          </summary>
          <ul className="timeline-mini">
            {req.history.map((h, i) => (
              <li key={i}>
                {fmtDateTime(h.at)} · {h.from_status ? `${h.from_status} → ` : ""}
                {h.to_status} by {h.actor ?? "system"}
                {h.comment ? ` — ${h.comment}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
      {(canReview || canWithdraw) && req.status === "PENDING" && (
        <div className="row" style={{ marginTop: 12 }}>
          {canReview && (
            <>
              <button className="btn btn-success btn-sm" onClick={() => setDeciding("APPROVED")}>
                Approve
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => setDeciding("REJECTED")}>
                Reject
              </button>
            </>
          )}
          {canWithdraw && (
            <button className="btn btn-sm" onClick={() => withdraw.mutate(req.id)} disabled={withdraw.isPending}>
              Withdraw request
            </button>
          )}
          {withdraw.isError && <span className="small notice notice-error">{errorMessage(withdraw.error)}</span>}
        </div>
      )}
      {deciding && <DecisionDialog req={req} decision={deciding} onClose={() => setDeciding(null)} />}
    </article>
  );
}

function DecisionDialog({
  req,
  decision,
  onClose,
}: {
  req: CondonationRequest;
  decision: "APPROVED" | "REJECTED";
  onClose: () => void;
}) {
  const [comment, setComment] = useState("");
  const decide = useDecideCondonation();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    decide.mutate({ id: req.id, decision, comment }, { onSuccess: onClose });
  };
  const verb = decision === "APPROVED" ? "Approve" : "Reject";
  return (
    <Modal title={`${verb} request from ${req.student.name}`} onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <p className="small muted">{req.reason}</p>
        <div className="field">
          <label htmlFor="decision-comment">
            Comment {decision === "REJECTED" ? "(required)" : "(optional)"}
          </label>
          <textarea
            id="decision-comment"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            required={decision === "REJECTED"}
            minLength={decision === "REJECTED" ? 3 : undefined}
            placeholder={decision === "REJECTED" ? "Explain why the request is rejected" : "e.g. Medical certificate verified"}
            autoFocus
          />
        </div>
        {decide.isError && <p className="notice notice-error small">{errorMessage(decide.error)}</p>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            className={`btn ${decision === "APPROVED" ? "btn-success" : "btn-danger"}`}
            disabled={decide.isPending}
          >
            {decide.isPending ? "Saving…" : `${verb} request`}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function CondonationForm({ analytics }: { analytics: StudentAnalytics }) {
  const [reason, setReason] = useState("");
  const [subjectId, setSubjectId] = useState<string>("");
  const submit = useSubmitCondonation();
  const atRisk =
    analytics.risk_level === "WARNING" ||
    analytics.risk_level === "CRITICAL";

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit.mutate(
      { reason: reason.trim(), subject_id: subjectId ? Number(subjectId) : null },
      { onSuccess: () => setReason("") },
    );
  };

  if (!atRisk) {
    return (
      <p className="notice notice-info small">
        Condonation requests open when your attendance is at risk (WARNING or CRITICAL). You are currently on track.
      </p>
    );
  }
  return (
    <form className="stack" onSubmit={onSubmit} aria-label="Submit condonation request">
      <div className="field">
        <label htmlFor="condonation-subject">Applies to</label>
        <select id="condonation-subject" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          <option value="">Overall attendance</option>
          {analytics.subjects.map((s) => (
            <option key={s.subject.id} value={s.subject.id}>
              {s.subject.name} ({pct(s.current_percentage)}, {s.risk_level.toLowerCase()})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="condonation-reason">Reason for absence</label>
        <textarea
          id="condonation-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          minLength={20}
          maxLength={2000}
          required
          placeholder="Explain the reason for the absences (e.g. medical leave with dates). At least 20 characters."
        />
        <span className="help">{reason.trim().length}/2000 characters (minimum 20)</span>
      </div>
      {submit.isError && <p className="notice notice-error small">{errorMessage(submit.error)}</p>}
      {submit.isSuccess && (
        <p className="notice notice-success small" role="status">
          Request submitted. Status: PENDING — your mentor has been notified.
        </p>
      )}
      <div>
        <button className="btn btn-primary" type="submit" disabled={submit.isPending || reason.trim().length < 20}>
          {submit.isPending ? "Submitting…" : "Submit condonation request"}
        </button>
      </div>
    </form>
  );
}
