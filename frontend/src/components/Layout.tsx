import { useEffect, useRef, useState, type ComponentType } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAlerts, useOverview } from "../api/hooks";
import type { Role } from "../api/types";
import { ROLE_LABEL, useAuth } from "../auth/AuthContext";
import {
  IconBell,
  IconDashboard,
  IconHome,
  IconLogout,
  IconReports,
  IconRequests,
  IconUpload,
  IconUsers,
} from "./icons";

interface NavItem {
  to: string;
  label: string;
  short: string; // label used in the phone bottom bar
  icon: ComponentType<{ size?: number }>;
  roles: Role[];
  badge?: "alerts" | "pending";
}

/** One list drives both the desktop top bar and the phone bottom bar (max 5 items per role). */
const NAV: NavItem[] = [
  { to: "/me", label: "My attendance", short: "Home", icon: IconHome, roles: ["STUDENT"] },
  { to: "/dashboard", label: "Dashboard", short: "Dashboard", icon: IconDashboard, roles: ["ADMIN", "MENTOR", "EXAM_CELL"] },
  { to: "/students", label: "Students", short: "Students", icon: IconUsers, roles: ["ADMIN", "MENTOR", "EXAM_CELL"] },
  { to: "/upload", label: "Upload", short: "Upload", icon: IconUpload, roles: ["ADMIN"] },
  { to: "/condonation", label: "Condonation", short: "Requests", icon: IconRequests, roles: ["ADMIN", "MENTOR", "EXAM_CELL", "STUDENT"], badge: "pending" },
  { to: "/reports", label: "Reports", short: "Reports", icon: IconReports, roles: ["ADMIN", "EXAM_CELL"] },
  { to: "/alerts", label: "Alerts", short: "Alerts", icon: IconBell, roles: ["STUDENT", "MENTOR"], badge: "alerts" },
];

function initials(name: string) {
  const parts = name.replace(/^(Dr|Prof)\.?\s+/i, "").split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const alerts = useAlerts();
  const overview = useOverview(!!user && user.role !== "STUDENT");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close the account menu on navigation, outside click or Escape.
  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  if (!user) return null;

  const counts = {
    alerts: alerts.data?.unread_count ?? 0,
    pending: user.role === "STUDENT" ? 0 : overview.data?.pending_condonations ?? 0,
  };
  const items = NAV.filter((n) => n.roles.includes(user.role));
  const scope = user.department ? user.department.code : user.role === "ADMIN" ? "All departments" : "";
  const signOut = async () => {
    setMenuOpen(false);
    await logout();
    navigate("/login", { replace: true });
  };
  const badge = (n: NavItem) =>
    n.badge && counts[n.badge] > 0 ? (
      <span className="nav-count" aria-label={`${counts[n.badge]} new`}>
        {counts[n.badge] > 99 ? "99+" : counts[n.badge]}
      </span>
    ) : null;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" aria-label="AttendAI home">
            <span className="brand-mark" aria-hidden="true">
              A
            </span>
            <span className="brand-text">
              <span className="brand-name">AttendAI</span>
              <span className="brand-sub">Attendance early warning</span>
            </span>
          </NavLink>

          <nav className="topnav" aria-label="Main navigation">
            {items.map((n) => (
              <NavLink key={n.to} to={n.to} className="topnav-link">
                <n.icon size={18} />
                <span>{n.label}</span>
                {badge(n)}
              </NavLink>
            ))}
          </nav>

          <div className="account" ref={menuRef}>
            <button
              type="button"
              className="account-button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label={`Account: ${user.name}`}
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span className="avatar" aria-hidden="true">
                {initials(user.name)}
              </span>
              <span className="account-text">
                <span className="account-name">{user.name}</span>
                <span className="account-role">
                  {ROLE_LABEL[user.role]}
                  {scope && ` · ${scope}`}
                </span>
              </span>
            </button>
            <button type="button" className="btn btn-sm signout-desktop" onClick={signOut}>
              <IconLogout size={16} />
              Sign out
            </button>
            {menuOpen && (
              <div className="account-menu" role="menu">
                <div className="account-menu-head">
                  <strong>{user.name}</strong>
                  <span className="small muted">{user.email}</span>
                  <span className="small muted">
                    {ROLE_LABEL[user.role]}
                    {scope && ` · ${scope}`}
                  </span>
                </div>
                <button type="button" role="menuitem" className="account-menu-item" onClick={signOut}>
                  <IconLogout size={18} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main id="main" className="main" tabIndex={-1}>
        <Outlet />
      </main>

      <nav className="bottomnav" aria-label="Main navigation" style={{ ["--items" as string]: items.length }}>
        {items.map((n) => (
          <NavLink key={n.to} to={n.to} className="bottomnav-link">
            <span className="bottomnav-icon">
              <n.icon size={22} />
              {badge(n)}
            </span>
            <span className="bottomnav-label">{n.short}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
