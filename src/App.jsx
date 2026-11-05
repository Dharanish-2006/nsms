import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
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
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="machines" element={<Navigate to="/" replace />} />
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
