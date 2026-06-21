import { Bot, Loader2, Trash2 } from "lucide-react";
import type { AgentSetting, DbUser } from "@/lib/api";

const formatUserLabel = (u: DbUser) =>
  [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;

const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};

interface AgentListTableProps {
  agents: AgentSetting[];
  users: DbUser[];
  loading: boolean;
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
  onDelete: (slug: string) => void;
}

export default function AgentListTable({
  agents,
  users,
  loading,
  selectedSlug,
  onSelect,
  onDelete,
}: AgentListTableProps) {
  const formatOwnerLabel = (email: string | null | undefined) => {
    if (!email) return "Unassigned";
    const owner = users.find((u) => u.email === email);
    return owner ? formatUserLabel(owner) : email;
  };

  return (
    <div className="rounded-2xl border border-zinc-800/60 bg-zinc-900/40 overflow-hidden shadow-sm backdrop-blur-sm transition hover:border-zinc-700/60">
      <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800/40">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-indigo-500/10 ring-1 ring-white/5">
            <Bot className="h-3.5 w-3.5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-100">Agents</h2>
          </div>
        </div>
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-500" />}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-zinc-950/40 text-[11px] uppercase tracking-wider text-zinc-500 border-b border-zinc-800/60">
            <tr>
              <th className="px-5 py-2.5 font-medium">Agent</th>
              <th className="px-5 py-2.5 font-medium">Owner</th>
              <th className="px-5 py-2.5 font-medium">Created</th>
              <th className="px-5 py-2.5 font-medium">Modified</th>
              <th className="px-5 py-2.5 font-medium">Published</th>
              <th className="px-5 py-2.5 font-medium text-right w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/40">
            {agents.map((a) => {
              const active = selectedSlug === a.slug;
              return (
                <tr
                  key={a.slug}
                  onClick={() => onSelect(a.slug)}
                  className={
                    "group cursor-pointer transition-all duration-150 " +
                    (active
                      ? "bg-indigo-500/[0.04]"
                      : "hover:bg-zinc-800/40")
                  }
                >
                  <td className="px-5 py-2.5 align-middle">
                    <div className="flex items-center gap-2.5">
                      <div className={`h-2 w-2 rounded-full shrink-0 ${active ? "bg-indigo-400" : "bg-zinc-600 group-hover:bg-zinc-500"}`} />
                      <div>
                        <div className="font-medium text-sm text-zinc-100 truncate">{a.name || a.slug}</div>
                        <div className="text-[11px] text-zinc-600 font-mono">{a.slug}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-2.5 align-middle text-zinc-400 text-sm">{formatOwnerLabel(a.created_by)}</td>
                  <td className="px-5 py-2.5 align-middle text-zinc-500 text-sm tabular-nums">{formatDateTime(a.created_at)}</td>
                  <td className="px-5 py-2.5 align-middle text-zinc-500 text-sm tabular-nums">{formatDateTime(a.updated_at)}</td>
                  <td className="px-5 py-2.5 align-middle">
                    {a.is_published ? (
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                        <span className="text-zinc-400 text-sm tabular-nums">{formatDateTime(a.published_at)}</span>
                      </div>
                    ) : (
                      <span className="text-zinc-600 text-sm">Not published</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5 align-middle text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(a.slug);
                      }}
                      className="rounded-lg p-1.5 text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition opacity-0 group-hover:opacity-100"
                      title="Delete agent"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
            {!loading && agents.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-14 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-800/60 ring-1 ring-white/5">
                      <Bot className="h-6 w-6 text-zinc-600" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-zinc-400">No agents configured yet</p>
                      <p className="text-xs text-zinc-600 mt-0.5">Create an agent to get started</p>
                    </div>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
