import { useEffect, useState } from "react";
import { api, type AgentSetting, type AgentSettingUpdate, type AgentSettingCreate, type KnowledgeSource, type DbUser } from "@/lib/api";
import AgentIcon from "@/components/AgentIcon";

const AVAILABLE_TOOLS = ["retrieve", "web_search", "create_jira_ticket"];

const DEFAULT_NEW_AGENT: AgentSettingCreate = {
  slug: "",
  name: "",
  description: "",
  llm_model: "gpt-5.4-nano",
  system_prompt: "",
  retrieval_top_k: 5,
  connected_sources: [],
  tools: ["retrieve", "web_search"],
  is_orchestrator: false,
  routes_to: [],
  visibility: "all",
  allowed_users: [],
};

export default function AdminAgents() {
  const [agents, setAgents] = useState<AgentSetting[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [users, setUsers] = useState<DbUser[]>([]);
  const [selected, setSelected] = useState<AgentSetting | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSettingCreate>({ ...DEFAULT_NEW_AGENT });
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [agentData, sourceData, userData] = await Promise.all([
        api.listAgentSettings(),
        api.listKnowledgeSources(),
        api.listUsers(),
      ]);
      setAgents(agentData);
      setSources(sourceData);
      setUsers(userData);
      if (selected) {
        const updated = agentData.find((a) => a.slug === selected.slug) ?? null;
        setSelected(updated);
      }
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const tools = selected.tools || [];
      const payload: AgentSettingUpdate = {
        name: selected.name || undefined,
        description: selected.description || undefined,
        llm_model: selected.llm_model || undefined,
        system_prompt: selected.system_prompt || undefined,
        retrieval_top_k: selected.retrieval_top_k,
        retrieval_enabled: tools.includes("retrieve"),
        web_search_enabled: tools.includes("web_search"),
        connected_sources: selected.connected_sources || undefined,
        tools: tools,
        is_orchestrator: selected.is_orchestrator,
        routes_to: selected.routes_to || undefined,
        visibility: selected.visibility || undefined,
        allowed_users: selected.allowed_users || undefined,
      };
      await api.updateAgentSetting(selected.slug, payload);
      await refresh();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const create = async () => {
    if (!newAgent.slug.trim()) {
      setError("Slug is required");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const tools = newAgent.tools || [];
      await api.createAgentSetting({
        ...newAgent,
        slug: newAgent.slug.trim(),
        name: newAgent.name?.trim() || undefined,
        description: newAgent.description?.trim() || undefined,
        system_prompt: newAgent.system_prompt?.trim() || undefined,
        retrieval_enabled: tools.includes("retrieve"),
        web_search_enabled: tools.includes("web_search"),
        is_orchestrator: newAgent.is_orchestrator,
        routes_to: newAgent.routes_to || undefined,
        visibility: newAgent.visibility || undefined,
        allowed_users: newAgent.allowed_users || undefined,
      });
      setShowCreate(false);
      setNewAgent({ ...DEFAULT_NEW_AGENT });
      await refresh();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const remove = async (slug: string) => {
    setError(null);
    try {
      await api.deleteAgentSetting(slug);
      if (selected?.slug === slug) setSelected(null);
      setDeleteConfirm(null);
      await refresh();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    }
  };

  const toggleTool = (agent: AgentSetting | AgentSettingCreate, tool: string) => {
    const current = agent.tools || [];
    const next = current.includes(tool)
      ? current.filter((t) => t !== tool)
      : [...current, tool];
    if ("id" in agent) {
      setSelected({ ...agent, tools: next });
    } else {
      setNewAgent({ ...agent, tools: next });
    }
  };

  const toggleRoute = (agent: AgentSetting | AgentSettingCreate, slug: string) => {
    const current = agent.routes_to || [];
    const next = current.includes(slug)
      ? current.filter((s) => s !== slug)
      : [...current, slug];
    if ("id" in agent) {
      setSelected({ ...agent, routes_to: next });
    } else {
      setNewAgent({ ...agent, routes_to: next });
    }
  };

  const toggleAllowedUser = (agent: AgentSetting | AgentSettingCreate, email: string) => {
    const current = agent.allowed_users || [];
    const next = current.includes(email)
      ? current.filter((e) => e !== email)
      : [...current, email];
    if ("id" in agent) {
      setSelected({ ...agent, allowed_users: next });
    } else {
      setNewAgent({ ...agent, allowed_users: next });
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Agents</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="text-sm bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded-md font-medium"
          >
            + Create Agent
          </button>
          <button
            onClick={refresh}
            className="text-sm bg-neutral-800 hover:bg-neutral-700 px-3 py-1.5 rounded-md"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 bg-red-900/30 border border-red-700/50 text-red-200 text-sm px-3 py-2 rounded-md">
          {error}
        </div>
      )}

      <div className="flex gap-4">
        {/* Agent list */}
        <div className="w-64 shrink-0 space-y-2">
          {loading && <p className="text-neutral-400 text-sm">Loading…</p>}
          {agents.map((a) => {
            const active = selected?.slug === a.slug;
            return (
              <div
                key={a.slug}
                className={
                  "group w-full text-left rounded-lg px-3 py-2 text-sm transition flex items-center gap-2.5 " +
                  (active
                    ? "bg-neutral-800 font-medium"
                    : "hover:bg-neutral-800/60 text-neutral-300 cursor-pointer")
                }
                onClick={() => setSelected(a)}
              >
                <div
                  className={
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border " +
                    (active
                      ? a.slug === "it"
                        ? "bg-cyan-500/10 border-cyan-500/30"
                        : a.slug === "hr"
                          ? "bg-rose-500/10 border-rose-500/30"
                          : "bg-indigo-500/10 border-indigo-500/30"
                      : "bg-neutral-900/60 border-neutral-700")
                  }
                >
                  <AgentIcon slug={a.slug} size={16} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{a.name || a.slug}</div>
                  <div className="text-xs text-neutral-500 truncate">{a.description || "-"}</div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteConfirm(a.slug);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-xs text-red-400 hover:text-red-300 px-1.5 py-0.5 rounded hover:bg-red-900/30 transition"
                  title="Delete agent"
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>

        {/* Detail panel */}
        <div className="flex-1 min-w-0">
          {selected ? (
            <div className="bg-neutral-800/60 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">{selected.name || selected.slug}</h2>
                <span className="text-xs text-neutral-500 uppercase">{selected.slug}</span>
              </div>

              <label className="block">
                <span className="text-xs text-neutral-400">Name</span>
                <input
                  value={selected.name || ""}
                  onChange={(e) => setSelected({ ...selected, name: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                />
              </label>

              <label className="block">
                <span className="text-xs text-neutral-400">Description</span>
                <textarea
                  value={selected.description || ""}
                  onChange={(e) => setSelected({ ...selected, description: e.target.value })}
                  rows={2}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                />
              </label>

              <label className="block">
                <span className="text-xs text-neutral-400">LLM Model</span>
                <input
                  value={selected.llm_model || ""}
                  onChange={(e) => setSelected({ ...selected, llm_model: e.target.value })}
                  placeholder="gpt-5.4-nano"
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                />
              </label>

              <label className="block">
                <span className="text-xs text-neutral-400">System Prompt</span>
                <textarea
                  value={selected.system_prompt || ""}
                  onChange={(e) => setSelected({ ...selected, system_prompt: e.target.value })}
                  rows={4}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                  placeholder="Define how this agent behaves..."
                />
              </label>

              <label className="block">
                <span className="text-xs text-neutral-400">Retrieval Top-K (1-20)</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={selected.retrieval_top_k}
                  onChange={(e) =>
                    setSelected({
                      ...selected,
                      retrieval_top_k: Math.min(20, Math.max(1, parseInt(e.target.value || "5", 10))),
                    })
                  }
                  className="w-24 bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                />
              </label>

              <div className="block">
                <span className="text-xs text-neutral-400">Tools</span>
                <div className="mt-1 flex flex-wrap gap-3">
                  {AVAILABLE_TOOLS.map((tool) => (
                    <label key={tool} className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={(selected.tools || []).includes(tool)}
                        onChange={() => toggleTool(selected, tool)}
                      />
                      <span className="capitalize">{tool.replace(/_/g, " ")}</span>
                    </label>
                  ))}
                </div>
              </div>

              <label className="block">
                <span className="text-xs text-neutral-400">Visibility</span>
                <select
                  value={selected.visibility || "all"}
                  onChange={(e) => setSelected({ ...selected, visibility: e.target.value })}
                  className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
                >
                  <option value="all">All users</option>
                  <option value="admin_only">Admins only</option>
                  <option value="restricted">Restricted to specific users</option>
                </select>
              </label>

              {selected.visibility === "restricted" && (
                <div className="block">
                  <span className="text-xs text-neutral-400">Allowed Users</span>
                  <div className="mt-1 space-y-1 max-h-40 overflow-y-auto bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2">
                    {users.length === 0 && (
                      <p className="text-xs text-neutral-500">No users found.</p>
                    )}
                    {users.map((u) => {
                      const checked = (selected.allowed_users || []).includes(u.email);
                      const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                      return (
                        <label key={u.id} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleAllowedUser(selected, u.email)}
                          />
                          <span>{display}</span>
                          <span className="text-xs text-neutral-500">{u.email}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected.is_orchestrator}
                  onChange={(e) => setSelected({ ...selected, is_orchestrator: e.target.checked })}
                />
                <span className="text-sm">Is Orchestrator (routes queries to other agents)</span>
              </label>

              {selected.is_orchestrator && (
                <div className="block">
                  <span className="text-xs text-neutral-400">Routes To</span>
                  <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2">
                    {agents.length <= 1 && (
                      <p className="text-xs text-neutral-500">No other agents available.</p>
                    )}
                    {agents
                      .filter((a) => a.slug !== selected.slug)
                      .map((a) => {
                        const checked = (selected.routes_to || []).includes(a.slug);
                        return (
                          <label key={a.slug} className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleRoute(selected, a.slug)}
                            />
                            <span>{a.name || a.slug}</span>
                            <span className="text-xs text-neutral-500">@{a.slug}</span>
                          </label>
                        );
                      })}
                  </div>
                </div>
              )}

              <div className="block">
                <span className="text-xs text-neutral-400">Connected Knowledge Sources</span>
                <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2">
                  {sources.length === 0 && (
                    <p className="text-xs text-neutral-500">No sources configured.</p>
                  )}
                  {sources.map((s) => {
                    const checked = (selected.connected_sources || []).includes(s.id);
                    return (
                      <label key={s.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const current = selected.connected_sources || [];
                            const next = checked
                              ? current.filter((x) => x !== s.id)
                              : [...current, s.id];
                            setSelected({ ...selected, connected_sources: next });
                          }}
                        />
                        <span>{s.name}</span>
                        <span className="text-xs text-neutral-500">({s.slug})</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={save}
                  disabled={saving}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-md text-sm font-medium"
                >
                  {saving ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </div>
          ) : (
            <p className="text-neutral-400 text-sm">Select an agent to configure.</p>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-lg space-y-3 max-h-[90vh] overflow-y-auto">
            <h2 className="font-semibold text-lg">Create New Agent</h2>

            <label className="block">
              <span className="text-xs text-neutral-400">Slug *</span>
              <input
                value={newAgent.slug}
                onChange={(e) => setNewAgent({ ...newAgent, slug: e.target.value })}
                placeholder="e.g. finance, legal, sales"
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              />
              <p className="text-xs text-neutral-500 mt-0.5">Unique identifier, no spaces.</p>
            </label>

            <label className="block">
              <span className="text-xs text-neutral-400">Name</span>
              <input
                value={newAgent.name}
                onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                placeholder="e.g. Finance Specialist"
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              />
            </label>

            <label className="block">
              <span className="text-xs text-neutral-400">Description</span>
              <textarea
                value={newAgent.description}
                onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                rows={2}
                placeholder="What this agent does..."
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              />
            </label>

            <label className="block">
              <span className="text-xs text-neutral-400">LLM Model</span>
              <input
                value={newAgent.llm_model}
                onChange={(e) => setNewAgent({ ...newAgent, llm_model: e.target.value })}
                placeholder="gpt-5.4-nano"
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              />
            </label>

            <label className="block">
              <span className="text-xs text-neutral-400">System Prompt</span>
              <textarea
                value={newAgent.system_prompt}
                onChange={(e) => setNewAgent({ ...newAgent, system_prompt: e.target.value })}
                rows={4}
                placeholder="Define how this agent behaves..."
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              />
            </label>

            <div className="block">
              <span className="text-xs text-neutral-400">Tools</span>
              <div className="mt-1 flex flex-wrap gap-3">
                {AVAILABLE_TOOLS.map((tool) => (
                  <label key={tool} className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={(newAgent.tools || []).includes(tool)}
                      onChange={() => toggleTool(newAgent, tool)}
                    />
                    <span className="capitalize">{tool.replace(/_/g, " ")}</span>
                  </label>
                ))}
              </div>
            </div>

            <label className="block">
              <span className="text-xs text-neutral-400">Visibility</span>
              <select
                value={newAgent.visibility || "all"}
                onChange={(e) => setNewAgent({ ...newAgent, visibility: e.target.value })}
                className="w-full bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2 text-sm mt-1"
              >
                <option value="all">All users</option>
                <option value="admin_only">Admins only</option>
                <option value="restricted">Restricted to specific users</option>
              </select>
            </label>

            {newAgent.visibility === "restricted" && (
              <div className="block">
                <span className="text-xs text-neutral-400">Allowed Users</span>
                <div className="mt-1 space-y-1 max-h-40 overflow-y-auto bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2">
                  {users.length === 0 && (
                    <p className="text-xs text-neutral-500">No users found.</p>
                  )}
                  {users.map((u) => {
                    const checked = (newAgent.allowed_users || []).includes(u.email);
                    const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                    return (
                      <label key={u.id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleAllowedUser(newAgent, u.email)}
                        />
                        <span>{display}</span>
                        <span className="text-xs text-neutral-500">{u.email}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={newAgent.is_orchestrator}
                onChange={(e) => setNewAgent({ ...newAgent, is_orchestrator: e.target.checked })}
              />
              <span className="text-sm">Is Orchestrator (routes queries to other agents)</span>
            </label>

            {newAgent.is_orchestrator && (
              <div className="block">
                <span className="text-xs text-neutral-400">Routes To</span>
                <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-neutral-950 border border-neutral-700 rounded-md px-3 py-2">
                  {agents.length === 0 && (
                    <p className="text-xs text-neutral-500">No other agents available.</p>
                  )}
                  {agents
                    .filter((a) => a.slug !== newAgent.slug)
                    .map((a) => {
                      const checked = (newAgent.routes_to || []).includes(a.slug);
                      return (
                        <label key={a.slug} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleRoute(newAgent, a.slug)}
                          />
                          <span>{a.name || a.slug}</span>
                          <span className="text-xs text-neutral-500">@{a.slug}</span>
                        </label>
                      );
                    })}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => { setShowCreate(false); setError(null); }}
                className="px-4 py-2 rounded-md text-sm bg-neutral-800 hover:bg-neutral-700"
              >
                Cancel
              </button>
              <button
                onClick={create}
                disabled={creating}
                className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-4 py-2 rounded-md text-sm font-medium"
              >
                {creating ? "Creating…" : "Create Agent"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-sm space-y-3">
            <h2 className="font-semibold">Delete Agent?</h2>
            <p className="text-sm text-neutral-400">
              Are you sure you want to delete <strong>{deleteConfirm}</strong>? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-md text-sm bg-neutral-800 hover:bg-neutral-700"
              >
                Cancel
              </button>
              <button
                onClick={() => remove(deleteConfirm)}
                className="bg-red-600 hover:bg-red-500 px-4 py-2 rounded-md text-sm font-medium"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
