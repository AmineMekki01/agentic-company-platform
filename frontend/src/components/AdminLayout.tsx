import { Link, Navigate, Outlet, useLocation } from "react-router-dom";
import { Bot, BookOpen, ChevronRight, HardDrive, LogOut, MessageSquare, Plug, Store, BarChart3, Activity } from "lucide-react";
import { useAuth } from "@/stores/auth";
import ThemeToggle from "@/components/ThemeToggle";

const navGroups = [
  {
    label: "Agents",
    items: [
      { to: "/admin/agents", label: "Agents", icon: Bot },
      { to: "/admin/agent-templates", label: "Templates", icon: Store },
    ],
  },
  {
    label: "Data & Integrations",
    items: [
      { to: "/admin/knowledge-sources", label: "Knowledge Sources", icon: BookOpen },
      { to: "/admin/connectors", label: "Connectors", icon: Plug },
      { to: "/admin/upload-settings", label: "Upload Settings", icon: HardDrive },
    ],
  },
  {
    label: "Analytics",
    items: [
      { to: "/admin/usage", label: "Usage", icon: BarChart3 },
    ],
  },
  {
    label: "Monitoring",
    items: [
      { to: "/admin/system-status", label: "System Status", icon: Activity },
    ],
  },
];

function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  if (segments.length <= 1) return null;

  const crumbs = segments.map((seg, i) => {
    const path = "/" + segments.slice(0, i + 1).join("/");
    const isLast = i === segments.length - 1;
    const label = seg.replace(/-/g, " ").replace(/_/g, " ");
    return (
      <span key={path} className="flex items-center gap-1.5">
        <ChevronRight className="h-3 w-3 text-tertiary" />
        {isLast ? (
          <span className="text-secondary font-medium capitalize">{label}</span>
        ) : (
          <Link to={path} className="text-tertiary hover:text-secondary transition capitalize">
            {label}
          </Link>
        )}
      </span>
    );
  });

  return (
    <nav className="flex items-center gap-0.5 text-xs mb-6">
      <Link to="/admin" className="text-tertiary hover:text-secondary transition">Admin</Link>
      {crumbs.slice(1)}
    </nav>
  );
}

export default function AdminLayout() {
  const auth = useAuth();
  const location = useLocation();

  if (!auth.isAdmin()) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="flex h-screen bg-canvas text-primary">
      {/* Sidebar */}
      <aside className="w-64 border-r border-line/60 bg-card backdrop-blur-sm flex flex-col">
        {/* Brand header */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-line/60">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20 ring-1 ring-white/10">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="font-semibold text-sm text-primary tracking-tight">Admin Panel</span>
            <p className="text-[10px] text-tertiary leading-none mt-0.5">Management Console</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-5">
              <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-tertiary">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((l) => {
                  const Icon = l.icon;
                  const active = location.pathname === l.to ||
                    (l.to === "/admin/agents" && location.pathname.startsWith("/admin/agents/"));
                  return (
                    <Link
                      key={l.to}
                      to={l.to}
                      className={
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200 " +
                        (active
                          ? "bg-brand/10 font-medium text-primary"
                          : "text-secondary hover:bg-hover hover:text-primary")
                      }
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-gradient-to-b from-indigo-400 to-violet-400" />
                      )}
                      <Icon className={`h-[18px] w-[18px] transition-colors ${active ? "text-brand" : "text-tertiary group-hover:text-secondary"}`} />
                      <span className="leading-tight">{l.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Back to chat */}
        <div className="flex items-center gap-2 px-3 pb-2 border-t border-line/60 pt-3">
          <Link
            to="/"
            className="group flex flex-1 items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-secondary hover:bg-hover hover:text-primary transition-all duration-200"
          >
            <MessageSquare className="h-[18px] w-[18px] text-tertiary group-hover:text-secondary transition-colors" />
            <span className="leading-tight">Back to Chat</span>
          </Link>
          <ThemeToggle />
        </div>

        {/* User profile + logout */}
        <div className="flex items-center gap-2.5 border-t border-line/60 px-4 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500/20 to-violet-500/20 text-xs font-semibold uppercase text-brand ring-1 ring-white/5">
            {auth.user?.email[0] ?? "?"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium text-secondary">{auth.user?.email}</p>
            <p className="text-[10px] uppercase tracking-wide text-tertiary">
              {auth.user?.role}
            </p>
          </div>
          <button
            onClick={auth.logout}
            className="rounded-lg p-1.5 text-tertiary transition hover:bg-hover hover:text-secondary"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gradient-to-b from-canvas to-canvas/95">
        <div className="mx-auto w-full p-8">
          <Breadcrumbs />
          <Outlet />
        </div>
      </main>
    </div>
  );
}
