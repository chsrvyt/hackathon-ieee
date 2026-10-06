import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { keys, useDemoAccounts } from "../api/hooks";
import { homePath, useAuth } from "../auth/AuthContext";
import { ServerSettings } from "../components/ServerSettings";
import { Loading } from "../components/ui";
import { getServerUrl, isNative } from "../native";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const native = isNative();
  const [serverReady, setServerReady] = useState(!native || !!getServerUrl());
  const demo = useDemoAccounts(serverReady);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) return <Loading label="Checking your session…" />;
  if (user) return <Navigate to={homePath(user.role)} replace />;

  const from = (location.state as { from?: string } | null)?.from;
  const signIn = async (e?: FormEvent, creds?: { email: string; password: string }) => {
    e?.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const u = await login(creds?.email ?? email.trim(), creds?.password ?? password);
      navigate(from && from !== "/login" ? from : homePath(u.role), { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-wrap">
      <section className="login-aside" aria-label="About AttendAI">
        <div className="row" style={{ gap: 12 }}>
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <strong style={{ fontSize: "1.1rem", color: "#fff" }}>AttendAI</strong>
        </div>
        <h1>Attendance Shortage Early Warning &amp; Condonation System</h1>
        <p>Don&apos;t just show attendance. Predict the shortage early and recommend the next action.</p>
        <ul>
          <li>Validated CSV / Excel attendance import</li>
          <li>Explainable projection and SAFE / WARNING / CRITICAL risk</li>
          <li>Exact recovery plan: how many classes to attend</li>
          <li>Mentor, HOD and Exam Cell views with condonation workflow</li>
        </ul>
      </section>
      <main className="login-main">
        <div className="login-card stack" style={{ gap: 18 }}>
          <div>
            <h1>{serverReady ? "Sign in" : "Welcome"}</h1>
            <p className="muted">
              {serverReady ? "Use your institutional account." : "First, connect the app to your college's AttendAI server."}
            </p>
          </div>
          {native && (
            <ServerSettings
              onChange={() => {
                setServerReady(true);
                setError(null);
                qc.invalidateQueries({ queryKey: keys.demo });
              }}
            />
          )}
          {serverReady && (
          <form className="card stack" onSubmit={signIn} aria-label="Sign in form">
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && (
              <p className="notice notice-error small" role="alert">
                {error}
              </p>
            )}
            <button className="btn btn-primary btn-block" type="submit" disabled={submitting}>
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
          )}

          {serverReady && demo.data?.enabled && (
            <section className="card stack" aria-labelledby="demo-heading" style={{ gap: 10 }}>
              <div>
                <h2 id="demo-heading">Demo accounts</h2>
                <p className="small muted">
                  Fictional data. Password for every account: <code>{demo.data.password}</code>
                </p>
              </div>
              <div className="demo-grid">
                {demo.data.accounts.map((a) => (
                  <button
                    key={a.email}
                    type="button"
                    className="btn"
                    disabled={submitting}
                    onClick={() => {
                      setEmail(a.email);
                      setPassword(demo.data!.password ?? "");
                      void signIn(undefined, { email: a.email, password: demo.data!.password ?? "" });
                    }}
                  >
                    <span>
                      <strong>{a.label}</strong>
                      <br />
                      <span className="muted">
                        {a.email.split("@")[0]}@<wbr />
                        {a.email.split("@")[1]}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
