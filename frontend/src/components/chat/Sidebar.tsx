import { Bot, LogOut, MessageSquare, Plus, Settings, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { Conversation } from "@/lib/api";
import { useAuth } from "@/stores/auth";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: SidebarProps) {
  const { user, logout, isAdmin } = useAuth();

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-zinc-800/70 bg-zinc-950">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-zinc-100">
          Company Platform
        </span>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl border border-zinc-700/80 bg-zinc-900/60 px-3 py-2.5 text-sm font-medium text-zinc-300 transition hover:bg-zinc-800/80 hover:text-zinc-100 hover:border-zinc-600"
        >
          <Plus className="h-4 w-4" />
          New chat
        </button>
      </div>

      <nav className="mt-3 flex-1 space-y-0.5 overflow-y-auto px-3 pb-4">
        {conversations.length === 0 && (
          <div className="px-3 py-8 text-center">
            <MessageSquare className="mx-auto mb-2 h-5 w-5 text-zinc-700" />
            <p className="text-xs text-zinc-600">No conversations yet</p>
          </div>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
              c.id === activeId
                ? "bg-zinc-800/80 text-zinc-100"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            }`}
            onClick={() => onSelect(c.id)}
          >
            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
            <span className="flex-1 truncate">{c.title ?? "New conversation"}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
              className="hidden shrink-0 text-zinc-500 hover:text-red-400 group-hover:block transition"
              aria-label="Delete conversation"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </nav>

      {isAdmin() && (
        <div className="px-3 py-2 border-t border-zinc-800/50">
          <Link
            to="/admin"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 transition"
          >
            <Settings className="h-4 w-4" />
            Admin Panel
          </Link>
        </div>
      )}
      <div className="flex items-center gap-2.5 border-t border-zinc-800/50 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-600 text-xs font-semibold uppercase text-zinc-200 ring-2 ring-zinc-800">
          {user?.email[0] ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-zinc-300">{user?.email}</p>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            {user?.role}
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-md p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-200"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
