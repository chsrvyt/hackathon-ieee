import { useEffect, useRef, useState } from "react";
import type { TimelinePoint } from "../api/types";
import { fmtDate, pct } from "./ui";

const H = 240;
const PAD = { top: 16, right: 16, bottom: 34, left: 40 };

const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** Track the rendered width so the SVG is drawn 1:1 and text stays legible at every screen size. */
function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Per-period attendance (bars) and cumulative attendance (line) against the target. */
export function TimelineChart({ points, target }: { points: TimelinePoint[]; target: number }) {
  const [ref, W] = useWidth<HTMLElement>(640);
  if (points.length === 0) return null;
  const values = points.flatMap((p) => [p.period_percentage ?? 100, p.cumulative_percentage ?? 100]);
  const lo = Math.max(0, Math.min(Math.floor((Math.min(...values, target) - 10) / 10) * 10, 60));
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (100 - lo)) * innerH;
  const step = innerW / points.length;
  const x = (i: number) => PAD.left + step * i + step / 2;
  const barW = Math.min(46, step * 0.5);
  const ticks = [];
  for (let t = lo; t <= 100; t += lo <= 40 ? 20 : 10) ticks.push(t);
  const line = points
    .map((p, i) => (p.cumulative_percentage === null ? null : `${x(i)},${y(p.cumulative_percentage)}`))
    .filter(Boolean)
    .join(" ");

  return (
    <figure className="chart" style={{ margin: 0 }} ref={ref}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="timeline-title timeline-desc">
        <title id="timeline-title">Attendance by reporting period</title>
        <desc id="timeline-desc">
          {points
            .map((p) => `${fmtDate(p.date)}: period ${pct(p.period_percentage)}, cumulative ${pct(p.cumulative_percentage)}`)
            .join("; ")}
        </desc>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke="#e6ebf1" />
            <text x={PAD.left - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#5e6b7e">
              {t}%
            </text>
          </g>
        ))}
        {points.map((p, i) =>
          p.period_percentage === null ? null : (
            <rect
              key={p.date}
              x={x(i) - barW / 2}
              y={y(p.period_percentage)}
              width={barW}
              height={Math.max(0, y(lo) - y(p.period_percentage))}
              rx="3"
              fill={p.period_percentage < target ? "#f2b8b3" : "#b9d3ee"}
            />
          ),
        )}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={y(target)}
          y2={y(target)}
          stroke="#b42318"
          strokeDasharray="6 4"
          strokeWidth="1.5"
        />
        <text x={W - PAD.right} y={y(target) - 5} fontSize="11" textAnchor="end" fill="#b42318" fontWeight="600">
          Target {target}%
        </text>
        <polyline points={line} fill="none" stroke="#1e3a5f" strokeWidth="2.5" />
        {points.map((p, i) =>
          p.cumulative_percentage === null ? null : (
            <circle key={p.date} cx={x(i)} cy={y(p.cumulative_percentage)} r="4" fill="#1e3a5f" />
          ),
        )}
        {points.map((p, i) => (
          <text key={p.date} x={x(i)} y={H - 12} fontSize="11" textAnchor="middle" fill="#5e6b7e">
            {shortDate(p.date)}
          </text>
        ))}
      </svg>
      <figcaption className="legend">
        <span>
          <i style={{ background: "#b9d3ee" }} />
          Attendance in period
        </span>
        <span>
          <i style={{ background: "#1e3a5f" }} />
          Cumulative attendance
        </span>
        <span>
          <i style={{ background: "#b42318" }} />
          Target
        </span>
      </figcaption>
    </figure>
  );
}
