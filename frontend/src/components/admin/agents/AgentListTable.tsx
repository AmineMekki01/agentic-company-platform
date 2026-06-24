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
    <div className="rounded-2xl border border-line/60 bg-card overflow-hidden shadow-sm backdrop-blur-sm transition hover:border-line">
      <div className="flex items-center justify-between px-5 py-4 border-b border-line/60">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-brand/10 ring-1 ring-line/60">
            <Bot className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-primary">Agents</h2>
          </div>
        </div>
        {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-tertiary" />}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-canvas text-[11px] uppercase tracking-wider text-tertiary border-b border-line/60">
            <tr>
              <th className="px-5 py-2.5 font-medium">Agent</th>
              <th className="px-5 py-2.5 font-medium">Owner</th>
              <th className="px-5 py-2.5 font-medium">Created</th>
              <th className="px-5 py-2.5 font-medium">Modified</th>
              <th className="px-5 py-2.5 font-medium">Published</th>
              <th className="px-5 py-2.5 font-medium text-right w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line/60">
            {agents.map((a) => {
              const active = selectedSlug === a.slug;
              return (
                <tr
                  key={a.slug}
                  onClick={() => onSelect(a.slug)}
                  className={
                    "group cursor-pointer transition-all duration-150 " +
                    (active
                      ? "bg-brand/[0.04]"
                      : "hover:bg-hover/70")
                  }
                >
                  <td className="px-5 py-2.5 align-middle">
                    <div className="flex items-center gap-2.5">
                      <div className={`h-2 w-2 rounded-full shrink-0 ${active ? "bg-brand" : "bg-tertiary group-hover:text-secondary"}`} />
                      <div>
                        <div className="font-medium text-sm text-primary truncate">{a.name || a.slug}</div>
                        <div className="text-[11px] text-tertiary font-mono">{a.slug}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-2.5 align-middle text-secondary text-sm">{formatOwnerLabel(a.created_by)}</td>
                  <td className="px-5 py-2.5 align-middle text-tertiary text-sm tabular-nums">{formatDateTime(a.created_at)}</td>
                  <td className="px-5 py-2.5 align-middle text-tertiary text-sm tabular-nums">{formatDateTime(a.updated_at)}</td>
                  <td className="px-5 py-2.5 align-middle">
                    {a.is_published ? (
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-success shrink-0" />
                        <span className="text-secondary text-sm tabular-nums">{formatDateTime(a.published_at)}</span>
                      </div>
                    ) : (
                      <span className="text-tertiary text-sm">Not published</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5 align-middle text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(a.slug);
                      }}
                      className="rounded-lg p-1.5 text-tertiary hover:text-danger hover:bg-danger-soft transition opacity-0 group-hover:opacity-100"
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
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-hover ring-1 ring-line/60">
                      <Bot className="h-6 w-6 text-tertiary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-secondary">No agents configured yet</p>
                      <p className="text-xs text-tertiary mt-0.5">Create an agent to get started</p>
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
