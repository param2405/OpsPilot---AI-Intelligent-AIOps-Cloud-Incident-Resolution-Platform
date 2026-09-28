import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DeepLearningPage } from "./pages/DeepLearningPage";
import { FoundationPage } from "./pages/FoundationPage";
import { HistoricalIncidentsPage } from "./pages/HistoricalIncidentsPage";
import { IncidentDetailsPage } from "./pages/IncidentDetailsPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { LaterPhasePage } from "./pages/LaterPhasePage";
import { LogsPage } from "./pages/LogsPage";
import { MetricsPage } from "./pages/MetricsPage";
import { MLEnginePage } from "./pages/MLEnginePage";
import { ModelPerformancePage } from "./pages/ModelPerformancePage";
import { RAGKnowledgePage } from "./pages/RAGKnowledgePage";
import { RemediationPage } from "./pages/RemediationPage";
import { SystemHealthPage } from "./pages/SystemHealthPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        {/* Core Production Surfaces (Phase 8 & 9) */}
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/:id" element={<IncidentDetailsPage />} />
        <Route path="/remediation" element={<RemediationPage />} />
        <Route path="/recommendations" element={<RemediationPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/historical-incidents" element={<HistoricalIncidentsPage />} />
        <Route path="/model-performance" element={<ModelPerformancePage />} />
        <Route path="/system-health" element={<SystemHealthPage />} />
        <Route path="/health" element={<SystemHealthPage />} />

        {/* Phase-specific Subsystem Explorer Surfaces */}
        <Route path="/foundation" element={<FoundationPage />} />
        <Route path="/ml" element={<MLEnginePage />} />
        <Route path="/deep-learning" element={<DeepLearningPage />} />
        <Route path="/rag" element={<RAGKnowledgePage />} />
        <Route path="/settings" element={<LaterPhasePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
