import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import type { Role } from "./api/types";
import { homePath, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { AlertsPage } from "./pages/AlertsPage";
import { CondonationPage } from "./pages/CondonationPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ReportsPage } from "./pages/ReportsPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";
import { StudentHomePage } from "./pages/StudentHomePage";
import { StudentsPage } from "./pages/StudentsPage";
import { UploadPage } from "./pages/UploadPage";

/** UX-only guard. Every API call is authorised again on the server. */
function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homePath(user.role)} replace />;
  return <>{children}</>;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return <Navigate to={user ? homePath(user.role) : "/login"} replace />;
}

const STAFF: Role[] = ["ADMIN", "MENTOR", "EXAM_CELL"];

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Home />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/me" element={<RequireAuth roles={["STUDENT"]}><StudentHomePage /></RequireAuth>} />
        <Route path="/dashboard" element={<RequireAuth roles={STAFF}><DashboardPage /></RequireAuth>} />
        <Route path="/students" element={<RequireAuth roles={STAFF}><StudentsPage /></RequireAuth>} />
        <Route path="/students/:id" element={<RequireAuth roles={STAFF}><StudentDetailPage /></RequireAuth>} />
        <Route path="/upload" element={<RequireAuth roles={["ADMIN"]}><UploadPage /></RequireAuth>} />
        <Route path="/condonation" element={<CondonationPage />} />
        <Route path="/reports" element={<RequireAuth roles={["ADMIN", "EXAM_CELL"]}><ReportsPage /></RequireAuth>} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
