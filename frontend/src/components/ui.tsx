import type { ReactNode } from "react";
import { errorMessage } from "../api/client";
import type { CondonationStatus, RiskLevel, Trend } from "../api/types";

export const pct = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? "—" : `${v.toFixed(digits)}%`;

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (iso: string | null | undefined) =>
  iso
    ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "—";

const RISK_TEXT: Record<RiskLevel, string> = {
  SAFE: "Safe",
  WARNING: "Warning",
  CRITICAL: "Critical",
  NO_DATA: "No data",
};
const RISK_ICON: Record<RiskLevel, string> = { SAFE: "✓", WARNING: "!", CRITICAL: "▲", NO_DATA: "–" };

export function RiskBadge({ level, large }: { level: RiskLevel; large?: boolean }) {
  return (
    <span className={`badge risk-${level}${large ? " badge-lg" : ""}`} title={`Risk level: ${RISK_TEXT[level]}`}>
      <span aria-hidden="true">{RISK_ICON[level]}</span>
      {RISK_TEXT[level].toUpperCase()}
    </span>
  );
}

const TREND_TEXT: Record<Trend, [string, string]> = {
  IMPROVING: ["↗", "Improving"],
  STABLE: ["→", "Stable"],
  DECREASING: ["↘", "Decreasing"],
  INSUFFICIENT_DATA: ["·", "Not enough history"],
};

export function TrendIndicator({ trend }: { trend: Trend }) {
  const [icon, text] = TREND_TEXT[trend];
  return (
    <span className={`trend trend-${trend}`}>
      <span aria-hidden="true">{icon}</span>
      {text}
    </span>
  );
}

export function StatusBadge({ status }: { status: CondonationStatus }) {
  return <span className={`badge status-${status}`}>{status}</span>;
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="state" role="alert">
      <h3>Could not load this section</h3>
      <p>{errorMessage(error)}</p>
      {onRetry && (
        <button className="btn btn-sm" style={{ marginTop: 12 }} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <h3>{title}</h3>
      {children && <div>{children}</div>}
    </div>
  );
}

export function Stat({
  label,
  value,
  foot,
  tone,
}: {
  label: string;
  value: ReactNode;
  foot?: ReactNode;
  tone?: "crit" | "warn" | "safe";
}) {
  return (
    <div className={`stat${tone ? ` ${tone}` : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {foot && <div className="stat-foot">{foot}</div>}
    </div>
  );
}

/** Attendance bar with a target marker. */
export function AttendanceBar({ value, target, level }: { value: number | null; target: number; level: RiskLevel }) {
  const width = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div
      className="pbar"
      role="img"
      aria-label={`Attendance ${pct(value)} against a ${pct(target, 0)} target`}
    >
      <div className={`pbar-fill ${level}`} style={{ width: `${width}%` }} />
      <div className="pbar-target" style={{ left: `${target}%` }} title={`Target ${target}%`} />
    </div>
  );
}

const LEVELS: RiskLevel[] = ["CRITICAL", "WARNING", "SAFE", "NO_DATA"];

export function RiskDistribution({ counts }: { counts: Record<RiskLevel, number> }) {
  const total = LEVELS.reduce((sum, l) => sum + (counts[l] ?? 0), 0);
  return (
    <div>
      <div
        className="dist"
        role="img"
        aria-label={LEVELS.map((l) => `${RISK_TEXT[l]} ${counts[l] ?? 0}`).join(", ")}
      >
        {total > 0 &&
          LEVELS.map((l) =>
            counts[l] ? <span key={l} className={`bg-${l}`} style={{ width: `${(counts[l] / total) * 100}%` }} /> : null,
          )}
      </div>
      <div className="legend">
        {LEVELS.filter((l) => l !== "NO_DATA" || counts[l]).map((l) => (
          <span key={l}>
            <i className={`bg-${l}`} />
            {RISK_TEXT[l]} <strong>{counts[l] ?? 0}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export function Histogram({ data, target }: { data: { bucket: string; count: number }[]; target: number }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <div className="hist" role="img" aria-label={data.map((d) => `${d.bucket}: ${d.count}`).join(", ")}>
      {data.map((d) => {
        const lower = parseFloat(d.bucket);
        const tone = lower >= target ? (lower >= target + 10 ? "SAFE" : "WARNING") : "CRITICAL";
        return (
          <div className="hist-col" key={d.bucket}>
            <span className="hist-count">{d.count}</span>
            <div className={`hist-bar bg-${tone}`} style={{ height: `${(d.count / max) * 100}%` }} />
            <span className="hist-label">{d.bucket}</span>
          </div>
        );
      })}
    </div>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2 style={{ marginBottom: 12 }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}
