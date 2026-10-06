import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAlerts, useOverview } from "../api/hooks";
import type { Role } from "../api/types";
import { ROLE_LABEL, useAuth } from "../auth/AuthContext";

interface NavItem {
  to: string;
  label: string;
  roles: Role[];
  badge?: "alerts" | "pending";
}

const NAV: NavItem[] = [
  { to: "/me", label: "My attendance", roles: ["STUDENT"] },
  { to: "/dashboard", label: "Dashboard", roles: ["ADMIN", "MENTOR", "EXAM_CELL"] },
  { to: "/students", label: "Students", roles: ["ADMIN", "MENTOR", "EXAM_CELL"] },
  { to: "/upload", label: "Upload attendance", roles: ["ADMIN"] },
  { to: "/condonation", label: "Condonation", roles: ["ADMIN", "MENTOR", "EXAM_CELL"], badge: "pending" },
  { to: "/reports", label: "Department reports", roles: ["ADMIN", "EXAM_CELL"] },
  { to: "/alerts", label: "Alerts", roles: ["STUDENT", "MENTOR"], badge: "alerts" },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const alerts = useAlerts();
  const overview = useOverview(!!user && user.role !== "STUDENT");
  if (!user) return null;

  const counts = {
    alerts: alerts.data?.unread_count ?? 0,
    pending: user.role === "STUDENT" ? 0 : overview.data?.pending_condonations ?? 0,
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Main navigation">
        <NavLink to="/" className="brand" aria-label="AttendAI home">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span>
            <div className="brand-name">AttendAI</div>
            <div className="brand-sub">Attendance early warning</div>
          </span>
        </NavLink>
        <nav className="nav">
          {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
            <NavLink key={n.to} to={n.to}>
              <span>{n.label}</span>
              {n.badge && counts[n.badge] > 0 && (
                <span className="nav-count" aria-label={`${counts[n.badge]} new`}>
                  {counts[n.badge]}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div>
            <div className="who">{user.name}</div>
            <div className="role">
              {ROLE_LABEL[user.role]}
              {user.department ? ` · ${user.department.code}` : user.role === "ADMIN" ? " · All departments" : ""}
            </div>
          </div>
          <button
            className="btn btn-sm"
            onClick={async () => {
              await logout();
              navigate("/login", { replace: true });
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
