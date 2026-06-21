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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100">Agents</h2>
          <p className="text-xs text-zinc-500">Click a row to edit that agent.</p>
        </div>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-zinc-800 text-left text-sm">
          <thead className="bg-zinc-950/60 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Owner</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium">Modified</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 bg-zinc-900">
            {agents.map((a) => {
              const active = selectedSlug === a.slug;
              return (
                <tr
                  key={a.slug}
                  onClick={() => onSelect(a.slug)}
                  className={
                    "cursor-pointer transition " +
                    (active ? "bg-zinc-800/70" : "hover:bg-zinc-800/50")
                  }
                >
                  <td className="px-4 py-3 align-top">
                    <div className="font-medium text-zinc-100 truncate">{a.name || a.slug}</div>
                  </td>
                  <td className="px-4 py-3 align-top text-zinc-300">{formatOwnerLabel(a.created_by)}</td>
                  <td className="px-4 py-3 align-top text-zinc-400">{formatDateTime(a.created_at)}</td>
                  <td className="px-4 py-3 align-top text-zinc-400">{formatDateTime(a.updated_at)}</td>
                  <td className="px-4 py-3 align-top text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(a.slug);
                      }}
                      className="rounded-md p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition"
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
                <td colSpan={5} className="px-4 py-10 text-center">
                  <Bot className="mx-auto h-8 w-8 text-zinc-700 mb-2" />
                  <p className="text-sm text-zinc-500">No agents configured yet</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
