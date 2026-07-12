import { useEffect } from "react";
import { Bot, Loader2, Plus } from "lucide-react";
import type { AgentSetting, AgentSettingCreate, DbUser, UploadSettings, ModelOption } from "@/lib/api";
import ToolsGrid from "./ToolsGrid";

interface CreateAgentPanelProps {
  open: boolean;
  onClose: () => void;
  agent: AgentSettingCreate;
  onChange: (agent: AgentSettingCreate) => void;
  onCreate: () => void;
  creating: boolean;
  users: DbUser[];
  models: ModelOption[];
  agents: AgentSetting[];
  currentUserEmail?: string;
  error: string | null;
  onClearError: () => void;
  uploadSettings?: UploadSettings | null;
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
  uploadSettings,
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
    <div className="animate-fade-in fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="animate-scale-in bg-card border border-line rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center gap-2 pb-3 border-b border-line">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10">
            <Bot className="h-4 w-4 text-brand" />
          </div>
          <h2 className="font-semibold text-lg text-primary">Create New Agent</h2>
        </div>

        {error && (
          <div className="bg-danger-soft border border-danger/30 text-danger text-sm px-3 py-2 rounded-lg flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-danger shrink-0" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs font-medium text-secondary">Slug *</span>
            <input
              value={agent.slug}
              onChange={(e) => onChange({ ...agent, slug: e.target.value })}
              placeholder="e.g. finance"
              className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
            />
            <p className="text-xs text-tertiary mt-0.5">Unique identifier, no spaces.</p>
          </label>
          <label className="block">
            <span className="text-xs font-medium text-secondary">Name</span>
            <input
              value={agent.name}
              onChange={(e) => onChange({ ...agent, name: e.target.value })}
              placeholder="e.g. Finance Specialist"
              className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-secondary">Description</span>
          <textarea
            value={agent.description}
            onChange={(e) => onChange({ ...agent, description: e.target.value })}
            rows={2}
            placeholder="What this agent does..."
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-secondary">Owner</span>
          <select
            value={agent.created_by || ""}
            onChange={(e) => onChange({ ...agent, created_by: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
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
          <p className="text-xs text-tertiary mt-1">
            Owner metadata only. All admins can manage every agent.
          </p>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-secondary">LLM Model</span>
          <select
            value={agent.llm_model || "gpt-5.4-nano"}
            onChange={(e) => onChange({ ...agent, llm_model: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          >
            {[...new Set(models.map((m) => m.provider))].map((prov) => (
              <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                {models.filter((m) => m.provider === prov).map((m) => (
                  <option key={m.name} value={m.name}>{m.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-secondary">System Prompt</span>
          <textarea
            value={agent.system_prompt}
            onChange={(e) => onChange({ ...agent, system_prompt: e.target.value })}
            rows={4}
            placeholder="Define how this agent behaves..."
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
          />
        </label>

        <div className="block">
          <span className="text-xs font-medium text-secondary">Tools</span>
          <div className="mt-2">
            <ToolsGrid
              selectedTools={agent.tools || []}
              values={{ web_search_max_results: agent.web_search_max_results, jira_tickets_limit: agent.jira_tickets_limit }}
              onToggle={(tool) => onChange(toggleTool(agent, tool))}
              onValueChange={(key, value) => onChange({ ...agent, [key]: value })}
            />
          </div>
        </div>

        <label
          className={`flex items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2.5 ${uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}
          title={
            uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket
              ? ""
              : "Go to Upload Settings and enable file uploads with an S3 connector + bucket first."
          }
        >
          <input
            type="checkbox"
            checked={agent.allow_uploads !== false}
            onChange={(e) => onChange({ ...agent, allow_uploads: e.target.checked })}
            disabled={!(uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket)}
            className="accent-brand"
          />
          <span>
            <span className="block text-sm font-medium text-primary">Allow file uploads</span>
            <span className="block text-xs text-tertiary">
              {uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket
                ? "Shows the attach button in chat when this agent is selected."
                : "Upload Settings must be configured (S3 connector + bucket) before enabling."}
            </span>
          </span>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-secondary">Visibility</span>
          <select
            value={agent.visibility || "all"}
            onChange={(e) => onChange({ ...agent, visibility: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          >
            <option value="all">All users</option>
            <option value="admin_only">Admins only</option>
            <option value="restricted">Restricted to specific users</option>
          </select>
        </label>

        {agent.visibility === "restricted" && (
          <div className="block">
            <span className="text-xs font-medium text-secondary">Allowed Users</span>
            <div className="mt-1 space-y-1 max-h-40 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
              {users.length === 0 && (
                <p className="text-xs text-tertiary">No users found.</p>
              )}
              {users.map((u) => {
                const checked = (agent.allowed_users || []).includes(u.email);
                const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                return (
                  <label key={u.id} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onChange(toggleAllowedUser(agent, u.email))}
                      className="accent-brand"
                    />
                    <span>{display}</span>
                    <span className="text-xs text-tertiary">{u.email}</span>
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
          <span className="text-sm text-secondary">Enable Routing (route to a specialist agent)</span>
        </label>

        {agent.is_router && (
          <div className="block">
            <span className="text-xs font-medium text-secondary">Routes To</span>
            <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
              {agents.length === 0 && (
                <p className="text-xs text-tertiary">No other agents available.</p>
              )}
              {agents
                .filter((a) => a.slug !== agent.slug)
                .map((a) => {
                  const checked = (agent.routes_to || []).includes(a.slug);
                  return (
                    <label key={a.slug} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onChange(toggleRoute(agent, a.slug))}
                        className="accent-warning"
                      />
                      <span>{a.name || a.slug}</span>
                      <span className="text-xs text-tertiary">@{a.slug}</span>
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
          <span className="text-sm text-secondary">Enable Orchestration (supervisor with child agents)</span>
        </label>

        {agent.is_orchestrator && (
          <div className="block">
            <span className="text-xs font-medium text-secondary">Child Agents</span>
            <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
              {agents.length === 0 && (
                <p className="text-xs text-tertiary">No other agents available.</p>
              )}
              {agents
                .filter((a) => a.slug !== agent.slug)
                .map((a) => {
                  const checked = (agent.routes_to || []).includes(a.slug);
                  return (
                    <label key={a.slug} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onChange(toggleRoute(agent, a.slug))}
                        className="accent-violet-500"
                      />
                      <span>{a.name || a.slug}</span>
                      <span className="text-xs text-tertiary">@{a.slug}</span>
                    </label>
                  );
                })}
            </div>
          </div>
        )}

        {/* Conscience: memory / emotions / episodes */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.memory_enabled || false}
            onChange={(e) => onChange({ ...agent, memory_enabled: e.target.checked })}
            className="accent-brand"
          />
          <span className="text-sm text-secondary">
            Enable Memory (facts, preferences, commitments, self-check)
          </span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.emotions_enabled || false}
            onChange={(e) => {
              const emotionsEnabled = e.target.checked;
              onChange({
                ...agent,
                emotions_enabled: emotionsEnabled,
                episodes_enabled: emotionsEnabled ? agent.episodes_enabled : false,
              });
            }}
            className="accent-brand"
          />
          <span className="text-sm text-secondary">
            Enable Emotions (persistent tone adaptation toward each user)
          </span>
        </label>

        <label
          className={`ml-6 flex items-center gap-2 ${
            agent.emotions_enabled ? "cursor-pointer" : "cursor-not-allowed opacity-50"
          }`}
        >
          <input
            type="checkbox"
            checked={agent.episodes_enabled || false}
            disabled={!agent.emotions_enabled}
            onChange={(e) => onChange({ ...agent, episodes_enabled: e.target.checked })}
            className="accent-brand"
          />
          <span className="text-sm text-secondary">
            Remember significant moments (requires Emotions)
          </span>
        </label>

        <div className="flex justify-end gap-2 pt-3 border-t border-line">
          <button
            onClick={() => { onClose(); onClearError(); }}
            className="px-4 py-2 rounded-lg text-sm bg-canvas hover:bg-hover border border-line text-secondary transition"
          >
            Cancel
          </button>
          <button
            onClick={onCreate}
            disabled={creating}
            className="flex items-center gap-1.5 bg-brand hover:bg-brand-hover disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-brand/15"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {creating ? "Creating…" : "Create Agent"}
          </button>
        </div>
      </div>
    </div>
  );
}
