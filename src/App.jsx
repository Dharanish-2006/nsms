import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { PageLoader } from "./components/PageState";
import { AuthProvider } from "./context/AuthContext";

// Each page is its own chunk, so the first screen downloads only what it needs.
const AuthPage = lazy(() => import("./pages/AuthPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ProcessPage = lazy(() => import("./pages/ProcessPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const AdminLayout = lazy(() =>
  import("./pages/admin/AdminLayout").then((m) => ({ default: m.AdminLayout })),
);
const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const AdminUsers = lazy(() => import("./pages/admin/AdminUsers"));
const AdminGateways = lazy(() => import("./pages/admin/AdminGateways"));
const AdminConnections = lazy(() => import("./pages/admin/AdminConnections"));
const AdminAudit = lazy(() => import("./pages/admin/AdminAudit"));
const AdminProfile = lazy(() => import("./pages/admin/AdminProfile"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route path="admin" element={<AdminLayout />}>
              <Route index element={<AdminDashboard />} />
              <Route path="users" element={<AdminUsers />} />
              <Route path="gateways" element={<AdminGateways />} />
              <Route path="connections" element={<AdminConnections />} />
              <Route path="audit" element={<AdminAudit />} />
              <Route path="profile" element={<AdminProfile />} />
            </Route>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="machines" element={<ProcessPage />} />
              <Route path="machines/:id" element={<ProcessPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="reports" element={<ReportsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </AuthProvider>
    </ErrorBoundary>
  );
}
