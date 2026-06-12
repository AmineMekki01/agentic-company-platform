import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { Bot, BookOpen, MessageSquare, Plug } from "lucide-react";
import { useAuth } from "@/stores/auth";

const links = [
  { to: "/admin/agents", label: "Agents", icon: Bot },
  { to: "/admin/knowledge-sources", label: "Knowledge Sources", icon: BookOpen },
  { to: "/admin/connectors", label: "Connectors", icon: Plug },
];

export default function AdminLayout() {
  const auth = useAuth();
  const location = useLocation();

  if (!auth.isAdmin()) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen bg-neutral-900 text-white">
      <aside className="w-56 border-r border-neutral-800 p-4 flex flex-col gap-1">
        <div className="font-bold text-lg mb-3 px-3">Admin</div>
        {links.map((l) => {
          const Icon = l.icon;
          const active = location.pathname === l.to;
          return (
            <Link
              key={l.to}
              to={l.to}
              className={
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition " +
                (active
                  ? "bg-neutral-800 font-medium text-white"
                  : "hover:bg-neutral-800/60 text-neutral-300")
              }
            >
              <Icon className={`h-4 w-4 ${active ? "text-indigo-400" : "text-neutral-400"}`} />
              {l.label}
            </Link>
          );
        })}
        <div className="mt-auto pt-4 border-t border-neutral-800">
          <Link
            to="/"
            className="flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-indigo-400 hover:bg-neutral-800/60 transition"
          >
            <MessageSquare className="h-4 w-4" />
            Back to Chat
          </Link>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
