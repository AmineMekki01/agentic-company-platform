import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Bot } from "lucide-react";

import AdminLayout from "@/components/AdminLayout";
import AdminAgentTemplates from "@/pages/AdminAgentTemplates";
import AdminAgents from "@/pages/AdminAgents";
import AdminConnectors from "@/pages/AdminConnectors";
import AdminHealth from "@/pages/AdminHealth";
import AdminKnowledgeSources from "@/pages/AdminKnowledgeSources";
import AdminUploadSettings from "@/pages/AdminUploadSettings";
import AdminUsage from "@/pages/AdminUsage";
import ChatPage from "@/pages/ChatPage";
import LoginPage from "@/pages/LoginPage";
import { useAuth } from "@/stores/auth";

function FullScreenSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <div className="flex flex-col items-center gap-4">
        <div className="relative flex h-14 w-14 items-center justify-center">
          <span className="absolute inset-0 animate-ping rounded-2xl bg-brand/20" />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-xl shadow-indigo-500/20 ring-1 ring-white/10">
            <Bot className="h-7 w-7 text-white" />
          </div>
        </div>
        <p className="text-sm text-tertiary">Loading your workspace…</p>
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
      <Route
        path="/:conversationId"
        element={user ? <ChatPage /> : <Navigate to="/login" replace />}
      />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="/admin/agents" replace />} />
        <Route path="agents" element={<AdminAgents />} />
        <Route path="agents/:agentSlug" element={<AdminAgents />} />
        <Route path="agent-templates" element={<AdminAgentTemplates />} />
        <Route path="knowledge-sources" element={<AdminKnowledgeSources />} />
        <Route path="connectors" element={<AdminConnectors />} />
        <Route path="system-status" element={<AdminHealth />} />
        <Route path="upload-settings" element={<AdminUploadSettings />} />
        <Route path="usage" element={<AdminUsage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
