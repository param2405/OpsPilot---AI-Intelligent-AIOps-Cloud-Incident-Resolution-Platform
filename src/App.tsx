import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { DeepLearningPage } from "./pages/DeepLearningPage";
import { FoundationPage } from "./pages/FoundationPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { InvestigationPage } from "./pages/InvestigationPage";
import { LaterPhasePage } from "./pages/LaterPhasePage";
import { LogsPage } from "./pages/LogsPage";
import { MetricsPage } from "./pages/MetricsPage";
import { MLEnginePage } from "./pages/MLEnginePage";
import { RAGKnowledgePage } from "./pages/RAGKnowledgePage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/foundation" element={<FoundationPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/ml" element={<MLEnginePage />} />
        <Route path="/deep-learning" element={<DeepLearningPage />} />
        <Route path="/rag" element={<RAGKnowledgePage />} />
        <Route path="/investigation" element={<InvestigationPage />} />
        <Route path="/recommendations" element={<InvestigationPage />} />
        <Route path="/settings" element={<LaterPhasePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
