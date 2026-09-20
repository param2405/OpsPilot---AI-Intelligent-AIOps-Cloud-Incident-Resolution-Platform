import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { FoundationPage } from "./pages/FoundationPage";
import { LaterPhasePage } from "./pages/LaterPhasePage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<FoundationPage />} />
        <Route path="/dashboard" element={<LaterPhasePage />} />
        <Route path="/incidents" element={<LaterPhasePage />} />
        <Route path="/metrics" element={<LaterPhasePage />} />
        <Route path="/logs" element={<LaterPhasePage />} />
        <Route path="/investigation" element={<LaterPhasePage />} />
        <Route path="/recommendations" element={<LaterPhasePage />} />
        <Route path="/settings" element={<LaterPhasePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
