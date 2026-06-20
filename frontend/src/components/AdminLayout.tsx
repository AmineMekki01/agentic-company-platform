import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { Bot, BookOpen, HardDrive, MessageSquare, Plug, Store } from "lucide-react";
import { useAuth } from "@/stores/auth";

const links = [
  { to: "/admin/agents", label: "Agents", icon: Bot },
  { to: "/admin/agent-templates", label: "Templates", icon: Store },
  { to: "/admin/knowledge-sources", label: "Knowledge Sources", icon: BookOpen },
  { to: "/admin/connectors", label: "Connectors", icon: Plug },
  { to: "/admin/upload-settings", label: "Upload Settings", icon: HardDrive },
];

export default function AdminLayout() {
  const auth = useAuth();
  const location = useLocation();

  if (!auth.isAdmin()) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100">
      <aside className="w-60 border-r border-zinc-800/80 bg-zinc-950 p-4 flex flex-col gap-0.5">
        <div className="flex items-center gap-2.5 px-3 py-3 mb-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <span className="font-semibold text-sm tracking-tight">Admin Panel</span>
        </div>
        <div className="space-y-0.5">
          {links.map((l) => {
            const Icon = l.icon;
            const active = location.pathname === l.to;
            return (
              <Link
                key={l.to}
                to={l.to}
                className={
                  "relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition " +
                  (active
                    ? "bg-zinc-900 font-medium text-zinc-100"
                    : "hover:bg-zinc-900/60 text-zinc-400 hover:text-zinc-200")
                }
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-indigo-500" />
                )}
                <Icon className={`h-4 w-4 ${active ? "text-indigo-400" : "text-zinc-500"}`} />
                {l.label}
              </Link>
            );
          })}
        </div>
        <div className="mt-auto pt-4 border-t border-zinc-800/60">
          <Link
            to="/"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900/60 hover:text-zinc-200 transition"
          >
            <MessageSquare className="h-4 w-4" />
            Back to Chat
          </Link>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-zinc-950 p-6">
        <Outlet />
      </main>
    </div>
  );
}
