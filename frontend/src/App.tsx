import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ScopeFooter } from "./components/ScopeFooter";
import { AuditPage } from "./pages/AuditPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { LiveRunPage } from "./pages/LiveRunPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { NewExperimentPage } from "./pages/NewExperimentPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ResultsPage } from "./pages/ResultsPage";

export default function App() {
  return (
    <div className="app-shell">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/experiments/new" element={<NewExperimentPage />} />
            <Route path="/experiments/:id/live" element={<LiveRunPage />} />
            <Route path="/experiments/:id" element={<ResultsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/methodology" element={<MethodologyPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ScopeFooter />
    </div>
  );
}
