import { useEffect } from "react";
import { Bot, Loader2, Plus } from "lucide-react";
import type { AgentSetting, AgentSettingCreate, DbUser } from "@/lib/api";

const AVAILABLE_TOOLS = ["web_search", "create_jira_ticket"];

interface CreateAgentPanelProps {
  open: boolean;
  onClose: () => void;
  agent: AgentSettingCreate;
  onChange: (agent: AgentSettingCreate) => void;
  onCreate: () => void;
  creating: boolean;
  users: DbUser[];
  models: string[];
  agents: AgentSetting[];
  currentUserEmail?: string;
  error: string | null;
  onClearError: () => void;
}

function toggleTool(agent: AgentSettingCreate, tool: string): AgentSettingCreate {
  const current = agent.tools || [];
  const next = current.includes(tool) ? current.filter((t) => t !== tool) : [...current, tool];
  return { ...agent, tools: next };
}

function toggleRoute(agent: AgentSettingCreate, slug: string): AgentSettingCreate {
  const current = agent.routes_to || [];
  const next = current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug];
  return { ...agent, routes_to: next };
}

function toggleAllowedUser(agent: AgentSettingCreate, email: string): AgentSettingCreate {
  const current = agent.allowed_users || [];
  const next = current.includes(email) ? current.filter((e) => e !== email) : [...current, email];
  return { ...agent, allowed_users: next };
}

export default function CreateAgentPanel({
  open,
  onClose,
  agent,
  onChange,
  onCreate,
  creating,
  users,
  models,
  agents,
  currentUserEmail,
  error,
  onClearError,
}: CreateAgentPanelProps) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center gap-2 pb-3 border-b border-zinc-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10">
            <Bot className="h-4 w-4 text-indigo-400" />
          </div>
          <h2 className="font-semibold text-lg">Create New Agent</h2>
        </div>

        {error && (
          <div className="bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-3 py-2 rounded-lg flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-zinc-400">Slug *</span>
            <input
              value={agent.slug}
              onChange={(e) => onChange({ ...agent, slug: e.target.value })}
              placeholder="e.g. finance"
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
            />
            <p className="text-xs text-zinc-500 mt-0.5">Unique identifier, no spaces.</p>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-zinc-400">Name</span>
            <input
              value={agent.name}
              onChange={(e) => onChange({ ...agent, name: e.target.value })}
              placeholder="e.g. Finance Specialist"
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-zinc-400">Description</span>
          <textarea
            value={agent.description}
            onChange={(e) => onChange({ ...agent, description: e.target.value })}
            rows={2}
            placeholder="What this agent does..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-400">Owner</span>
          <select
            value={agent.created_by || ""}
            onChange={(e) => onChange({ ...agent, created_by: e.target.value })}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          >
            <option value="">Use current admin as owner ({currentUserEmail || "unknown"})</option>
            {users.map((u) => {
              const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
              return (
                <option key={u.id} value={u.email}>
                  {display} — {u.email}
                </option>
              );
            })}
          </select>
          <p className="text-xs text-zinc-500 mt-1">
            Owner metadata only. All admins can manage every agent.
          </p>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-400">LLM Model</span>
          <select
            value={agent.llm_model || "gpt-5.4-nano"}
            onChange={(e) => onChange({ ...agent, llm_model: e.target.value })}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          >
            {models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-400">System Prompt</span>
          <textarea
            value={agent.system_prompt}
            onChange={(e) => onChange({ ...agent, system_prompt: e.target.value })}
            rows={4}
            placeholder="Define how this agent behaves..."
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
          />
        </label>

        <div className="block">
          <span className="text-xs font-medium text-zinc-400">Tools</span>
          <div className="mt-2 flex flex-wrap gap-3">
            {AVAILABLE_TOOLS.map((tool) => (
              <label key={tool} className="flex items-center gap-1.5 text-sm text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={(agent.tools || []).includes(tool)}
                  onChange={() => onChange(toggleTool(agent, tool))}
                  className="accent-indigo-500"
                />
                <span className="capitalize">{tool.replace(/_/g, " ")}</span>
              </label>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2.5">
          <input
            type="checkbox"
            checked={agent.allow_uploads !== false}
            onChange={(e) => onChange({ ...agent, allow_uploads: e.target.checked })}
            className="accent-indigo-500"
          />
          <span>
            <span className="block text-sm font-medium text-zinc-200">Allow file uploads</span>
            <span className="block text-xs text-zinc-500">
              Shows the attach button in chat when this agent is selected.
            </span>
          </span>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-zinc-400">Visibility</span>
          <select
            value={agent.visibility || "all"}
            onChange={(e) => onChange({ ...agent, visibility: e.target.value })}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          >
            <option value="all">All users</option>
            <option value="admin_only">Admins only</option>
            <option value="restricted">Restricted to specific users</option>
          </select>
        </label>

        {agent.visibility === "restricted" && (
          <div className="block">
            <span className="text-xs font-medium text-zinc-400">Allowed Users</span>
            <div className="mt-1 space-y-1 max-h-40 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
              {users.length === 0 && (
                <p className="text-xs text-zinc-500">No users found.</p>
              )}
              {users.map((u) => {
                const checked = (agent.allowed_users || []).includes(u.email);
                const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                return (
                  <label key={u.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-800 rounded-md px-1 py-0.5 transition">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onChange(toggleAllowedUser(agent, u.email))}
                      className="accent-indigo-500"
                    />
                    <span>{display}</span>
                    <span className="text-xs text-zinc-500">{u.email}</span>
                  </label>
                );
              })}
            </div>
          </div>
        )}

        {/* Routing */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.is_router}
            onChange={(e) => onChange({ ...agent, is_router: e.target.checked, is_orchestrator: false })}
            className="accent-amber-500"
          />
          <span className="text-sm text-zinc-300">Enable Routing (route to a specialist agent)</span>
        </label>

        {agent.is_router && (
          <div className="block">
            <span className="text-xs font-medium text-zinc-400">Routes To</span>
            <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
              {agents.length === 0 && (
                <p className="text-xs text-zinc-500">No other agents available.</p>
              )}
              {agents
                .filter((a) => a.slug !== agent.slug)
                .map((a) => {
                  const checked = (agent.routes_to || []).includes(a.slug);
                  return (
                    <label key={a.slug} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-800 rounded-md px-1 py-0.5 transition">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onChange(toggleRoute(agent, a.slug))}
                        className="accent-amber-500"
                      />
                      <span>{a.name || a.slug}</span>
                      <span className="text-xs text-zinc-500">@{a.slug}</span>
                    </label>
                  );
                })}
            </div>
          </div>
        )}

        {/* Orchestration */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.is_orchestrator}
            onChange={(e) => onChange({ ...agent, is_orchestrator: e.target.checked, is_router: false })}
            className="accent-violet-500"
          />
          <span className="text-sm text-zinc-300">Enable Orchestration (supervisor with child agents)</span>
        </label>

        {agent.is_orchestrator && (
          <div className="block">
            <span className="text-xs font-medium text-zinc-400">Child Agents</span>
            <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
              {agents.length === 0 && (
                <p className="text-xs text-zinc-500">No other agents available.</p>
              )}
              {agents
                .filter((a) => a.slug !== agent.slug)
                .map((a) => {
                  const checked = (agent.routes_to || []).includes(a.slug);
                  return (
                    <label key={a.slug} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-800 rounded-md px-1 py-0.5 transition">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onChange(toggleRoute(agent, a.slug))}
                        className="accent-violet-500"
                      />
                      <span>{a.name || a.slug}</span>
                      <span className="text-xs text-zinc-500">@{a.slug}</span>
                    </label>
                  );
                })}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
          <button
            onClick={() => { onClose(); onClearError(); }}
            className="px-4 py-2 rounded-lg text-sm bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition"
          >
            Cancel
          </button>
          <button
            onClick={onCreate}
            disabled={creating}
            className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-500/15"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {creating ? "Creating…" : "Create Agent"}
          </button>
        </div>
      </div>
    </div>
  );
}
