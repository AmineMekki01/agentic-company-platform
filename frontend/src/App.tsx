import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";

import AdminLayout from "@/components/AdminLayout";
import AdminAgents from "@/pages/AdminAgents";
import AdminConnectors from "@/pages/AdminConnectors";
import AdminKnowledgeSources from "@/pages/AdminKnowledgeSources";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import { useAuth } from "@/stores/auth";

function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
    </div>
  );
}

export default function App() {
  const { user, loading, restore } = useAuth();

  useEffect(() => {
    restore();
  }, [restore]);

  if (loading) return <FullScreenSpinner />;

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={user ? <ChatPage /> : <Navigate to="/login" replace />}
      />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="/admin/agents" replace />} />
        <Route path="agents" element={<AdminAgents />} />
        <Route path="knowledge-sources" element={<AdminKnowledgeSources />} />
        <Route path="connectors" element={<AdminConnectors />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
