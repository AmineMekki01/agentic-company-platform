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
    <div className="flex min-h-screen items-center justify-center bg-zinc-950">
      <div className="flex flex-col items-center gap-3">
        <div className="relative flex h-10 w-10 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
        </div>
        <p className="text-sm text-zinc-500">Loading…</p>
      </div>
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
