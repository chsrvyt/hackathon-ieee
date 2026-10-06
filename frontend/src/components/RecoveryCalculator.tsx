import { useEffect, useState } from "react";
import { useRecoveryCalc } from "../api/hooks";
import { errorMessage } from "../api/client";
import { pct } from "./ui";

interface Props {
  attended: number;
  conducted: number;
  target: number;
  remaining: number;
}

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** What-if calculator. The maths runs server-side (same function the risk engine uses). */
export function RecoveryCalculator(props: Props) {
  const [form, setForm] = useState({
    attended: String(props.attended),
    conducted: String(props.conducted),
    target: String(props.target),
    remaining: String(props.remaining),
  });
  const debounced = useDebounced(form);
  const parsed = {
    attended: Number(debounced.attended),
    conducted: Number(debounced.conducted),
    target: Number(debounced.target),
    remaining: Number(debounced.remaining),
  };
  const valid =
    [parsed.attended, parsed.conducted, parsed.remaining].every((n) => Number.isInteger(n) && n >= 0) &&
    parsed.target > 0 &&
    parsed.target <= 100 &&
    parsed.attended <= parsed.conducted;
  const query = useRecoveryCalc(valid ? parsed : null);
  const result = query.data;

  const field = (key: keyof typeof form, label: string, help?: string) => (
    <div className="field">
      <label htmlFor={`calc-${key}`}>{label}</label>
      <input
        id={`calc-${key}`}
        type="number"
        inputMode="numeric"
        min={key === "target" ? 1 : 0}
        max={key === "target" ? 100 : undefined}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      />
      {help && <span className="help">{help}</span>}
    </div>
  );

  return (
    <section className="card" aria-labelledby="calc-heading">
      <div className="card-head">
        <h2 id="calc-heading">Recovery calculator</h2>
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() =>
            setForm({
              attended: String(props.attended),
              conducted: String(props.conducted),
              target: String(props.target),
              remaining: String(props.remaining),
            })
          }
        >
          Reset
        </button>
      </div>
      <div className="grid grid-2" style={{ gap: 10 }}>
        {field("attended", "Classes attended")}
        {field("conducted", "Classes conducted")}
        {field("target", "Target %")}
        {field("remaining", "Classes left this term")}
      </div>
      <div aria-live="polite" style={{ marginTop: 14 }}>
        {!valid ? (
          <p className="notice notice-error small">
            Enter whole numbers; attended cannot exceed conducted and the target must be between 1 and 100.
          </p>
        ) : query.isError ? (
          <p className="notice notice-error small">{errorMessage(query.error)}</p>
        ) : result ? (
          <div className="stack" style={{ gap: 6 }}>
            <p>
              Current: <strong>{pct(result.current_percentage)}</strong>
              {result.classes_required !== null && result.classes_required > 0 && (
                <>
                  {" "}
                  · Classes needed in a row: <strong>{result.classes_required}</strong>
                </>
              )}
            </p>
            <p className={`notice ${result.possible ? "notice-info" : "notice-warn"} small`}>{result.message}</p>
          </div>
        ) : (
          <p className="small muted">Calculating…</p>
        )}
      </div>
    </section>
  );
}
