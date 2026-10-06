import { useState, type FormEvent } from "react";
import { DEFAULT_SERVER_URL, checkServer, getServerUrl, normalise, setServerUrl } from "../native";
import { IconServer } from "./icons";

const EXAMPLE = DEFAULT_SERVER_URL.replace(/^https?:\/\//, "") || "attendai.example.edu";
const looksLikeEmail = (value: string) => /^[^\s/:@]+@[^\s/:@]+$/.test(value.trim());

/** Android app only: choose which AttendAI server the app talks to. */
export function ServerSettings({ onChange }: { onChange: () => void }) {
  const current = getServerUrl();
  const [editing, setEditing] = useState(!current);
  const [value, setValue] = useState(current);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (looksLikeEmail(value)) {
      setError(`That is an email address. Enter the server address here (for example ${EXAMPLE}); you sign in with your email on the next step.`);
      return;
    }
    const { url, error: invalid } = normalise(value);
    if (!url) {
      setError(invalid ?? "Invalid address.");
      return;
    }
    setChecking(true);
    setError(null);
    const ok = await checkServer(url);
    setChecking(false);
    if (!ok) {
      setError(`No AttendAI server answered at ${url}. Check the address and your connection.`);
      return;
    }
    setServerUrl(url);
    setValue(url);
    setEditing(false);
    onChange();
  };

  if (!editing) {
    return (
      <div className="server-chip">
        <IconServer size={18} />
        <span className="small">
          Server: <strong>{current.replace(/^https?:\/\//, "")}</strong>
        </span>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setEditing(true)}>
          Change
        </button>
      </div>
    );
  }
  return (
    <form className="card stack" onSubmit={save} aria-label="Choose server">
      <div>
        <h2>Connect to your institution</h2>
        <p className="small muted">Enter the AttendAI website address given by your college, e.g. {EXAMPLE}</p>
      </div>
      <div className="field">
        <label htmlFor="server-url">Server address</label>
        <input
          id="server-url"
          type="text"
          inputMode="url"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          placeholder={EXAMPLE}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          required
        />
      </div>
      {error && (
        <p className="notice notice-error small" role="alert">
          {error}
        </p>
      )}
      <div className="row">
        <button className="btn btn-primary" type="submit" disabled={checking}>
          {checking ? "Checking…" : "Connect"}
        </button>
        {current && (
          <button type="button" className="btn btn-ghost" onClick={() => setEditing(false)}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
