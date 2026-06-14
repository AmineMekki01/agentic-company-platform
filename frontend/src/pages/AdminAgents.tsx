import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Save, Trash2, Bot, Settings, BookOpen, Wrench, Rocket, Globe, ChevronLeft } from "lucide-react";
import { api, type AgentSetting, type AgentSettingUpdate, type AgentSettingCreate, type KnowledgeSource, type DbUser } from "@/lib/api";
import AgentIcon from "@/components/AgentIcon";
import { useAuth } from "@/stores/auth";

type TabKey = "overview" | "tools" | "knowledge" | "orchestration" | "deploy";

const TABS: { key: TabKey; label: string; icon: typeof Settings }[] = [
  { key: "overview", label: "Overview", icon: Settings },
  { key: "tools", label: "Tools", icon: Wrench },
  { key: "knowledge", label: "Knowledge", icon: BookOpen },
  { key: "orchestration", label: "Orchestration", icon: Rocket },
  { key: "deploy", label: "Deploy", icon: Globe },
];

const AVAILABLE_TOOLS = ["web_search", "create_jira_ticket"];

const DEFAULT_NEW_AGENT: AgentSettingCreate = {
  slug: "",
  name: "",
  description: "",
  llm_model: "gpt-5.4-nano",
  system_prompt: "",
  retrieval_top_k: 5,
  connected_sources: [],
  tools: [],
  is_orchestrator: false,
  routes_to: [],
  visibility: "all",
  created_by: "",
  allowed_users: [],
};

const formatUserLabel = (u: DbUser) => [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;

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

const makeDefaultNewAgent = (ownerEmail = ""): AgentSettingCreate => ({
  ...DEFAULT_NEW_AGENT,
  created_by: ownerEmail,
});

export default function AdminAgents() {
  const { user: currentUser } = useAuth();
  const [agents, setAgents] = useState<AgentSetting[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [users, setUsers] = useState<DbUser[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [selected, setSelected] = useState<AgentSetting | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSettingCreate>(() => makeDefaultNewAgent());
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  const closeSelected = () => {
    setSelected(null);
    setActiveTab("overview");
  };

  const formatOwnerLabel = (email: string | null | undefined) => {
    if (!email) return "Unassigned";
    const owner = users.find((u) => u.email === email);
    return owner ? formatUserLabel(owner) : email;
  };

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [agentData, sourceData, userData, modelData] = await Promise.all([
        api.listAgentSettings(),
        api.listKnowledgeSources(),
        api.listUsers(),
        api.listModels(),
      ]);
      setAgents(agentData);
      setSources(sourceData);
      setUsers(userData);
      setModels(modelData);
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
      const tools = (selected.tools || []).filter((t) => t !== "retrieve");
      const payload: AgentSettingUpdate = {
        name: selected.name || undefined,
        description: selected.description || undefined,
        llm_model: selected.llm_model || undefined,
        system_prompt: selected.system_prompt || undefined,
        retrieval_top_k: selected.retrieval_top_k,
        retrieval_enabled: (selected.connected_sources || []).length > 0,
        web_search_enabled: tools.includes("web_search"),
        connected_sources: selected.connected_sources || undefined,
        tools: tools,
        is_orchestrator: selected.is_orchestrator,
        routes_to: selected.routes_to || undefined,
        visibility: selected.visibility || undefined,
        created_by: selected.created_by || undefined,
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
      const tools = (newAgent.tools || []).filter((t) => t !== "retrieve");
      await api.createAgentSetting({
        ...newAgent,
        slug: newAgent.slug.trim(),
        name: newAgent.name?.trim() || undefined,
        description: newAgent.description?.trim() || undefined,
        system_prompt: newAgent.system_prompt?.trim() || undefined,
        created_by: newAgent.created_by?.trim() || undefined,
        retrieval_enabled: (newAgent.connected_sources || []).length > 0,
        web_search_enabled: tools.includes("web_search"),
        is_orchestrator: newAgent.is_orchestrator,
        routes_to: newAgent.routes_to || undefined,
        visibility: newAgent.visibility || undefined,
        allowed_users: newAgent.allowed_users || undefined,
      });
      setShowCreate(false);
      setNewAgent(makeDefaultNewAgent(currentUser?.email || ""));
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
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-zinc-500 mt-0.5">Configure and manage AI agents for your workspace</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowCreate(true); setError(null); setNewAgent(makeDefaultNewAgent(currentUser?.email || "")); }}
            className="flex items-center gap-1.5 text-sm bg-indigo-600 hover:bg-indigo-500 px-3 py-2 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
          >
            <Plus className="h-3.5 w-3.5" />
            Create Agent
          </button>
          <button
            onClick={refresh}
            className="flex items-center gap-1.5 text-sm bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 px-3 py-2 rounded-lg transition"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex gap-4">
        {/* Agents table */}
        <div className={selected ? "hidden" : "w-full"}>
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
                    const active = selected?.slug === a.slug;
                    return (
                      <tr
                        key={a.slug}
                        onClick={() => { setSelected(a); setActiveTab("overview"); }}
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
                              setDeleteConfirm(a.slug);
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
        </div>

        {/* Detail panel */}
        <div className={selected ? "flex-1 min-w-0" : "hidden"}>
          {selected ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl shadow-sm flex flex-col h-full">
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
                <div className="flex items-center gap-3 min-w-0">
                  <button
                    onClick={closeSelected}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 transition hover:bg-zinc-800"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back to list
                  </button>
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                      <AgentIcon slug={selected.slug} size={18} />
                    </div>
                    <div>
                      <h2 className="font-semibold text-zinc-100">{selected.name || selected.slug}</h2>
                      <span className="text-xs text-zinc-500 uppercase tracking-wide">{selected.slug}</span>
                      <div className="mt-1 text-xs text-zinc-500">
                        Owner: <span className="text-zinc-300">{formatOwnerLabel(selected.created_by)}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="text-xs text-zinc-500">
                  Owner: <span className="text-zinc-300">{formatOwnerLabel(selected.created_by)}</span>
                </div>
              </div>

              <div className="flex flex-1 min-h-0">
                <div className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-950/40 p-3">
                  <div className="mb-3 px-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                    Sections
                  </div>
                  <div className="space-y-1">
                    {TABS.map((t) => {
                      const Icon = t.icon;
                      const active = activeTab === t.key;
                      return (
                        <button
                          key={t.key}
                          onClick={() => setActiveTab(t.key)}
                          className={
                            "flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition " +
                            (active
                              ? "border-zinc-800 bg-zinc-900 font-medium text-zinc-100"
                              : "border-transparent text-zinc-500 hover:border-zinc-800 hover:bg-zinc-900/60 hover:text-zinc-200")
                          }
                        >
                          <Icon className={"h-4 w-4 " + (active ? "text-indigo-400" : "text-zinc-500")} />
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

              {/* Tab content */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {activeTab === "overview" && (
                  <>
                    <div className="grid grid-cols-2 gap-4">
                      <label className="block">
                        <span className="text-xs font-medium text-zinc-400">Name</span>
                        <input
                          value={selected.name || ""}
                          onChange={(e) => setSelected({ ...selected, name: e.target.value })}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                        />
                      </label>
                      <label className="block">
                        <span className="text-xs font-medium text-zinc-400">LLM Model</span>
                        <select
                          value={selected.llm_model || "gpt-5.4-nano"}
                          onChange={(e) => setSelected({ ...selected, llm_model: e.target.value })}
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                        >
                          {models.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <label className="block">
                      <span className="text-xs font-medium text-zinc-400">Description</span>
                      <textarea
                        value={selected.description || ""}
                        onChange={(e) => setSelected({ ...selected, description: e.target.value })}
                        rows={2}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
                      />
                    </label>

                    <label className="block">
                      <span className="text-xs font-medium text-zinc-400">Owner</span>
                      <select
                        value={selected.created_by || ""}
                        onChange={(e) => setSelected({ ...selected, created_by: e.target.value })}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                      >
                        <option value="">Keep existing owner</option>
                        {users.map((u) => (
                          <option key={u.id} value={u.email}>
                            {formatUserLabel(u)} — {u.email}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="text-xs font-medium text-zinc-400">Instructions (System Prompt)</span>
                      <textarea
                        value={selected.system_prompt || ""}
                        onChange={(e) => setSelected({ ...selected, system_prompt: e.target.value })}
                        rows={5}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
                        placeholder="Define how this agent behaves, what it can do, and how it should respond..."
                      />
                    </label>

                  </>
                )}

                {activeTab === "tools" && (
                  <div className="space-y-4">
                    <div className="block">
                      <span className="text-xs font-medium text-zinc-400">Enabled Tools</span>
                      <div className="mt-2 flex flex-wrap gap-3">
                        {AVAILABLE_TOOLS.map((tool) => (
                          <label key={tool} className="flex items-center gap-1.5 text-sm text-zinc-300 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={(selected.tools || []).includes(tool)}
                              onChange={() => toggleTool(selected, tool)}
                              className="accent-indigo-500"
                            />
                            <span className="capitalize">{tool.replace(/_/g, " ")}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "orchestration" && (
                  <div className="space-y-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selected.is_orchestrator}
                        onChange={(e) => setSelected({ ...selected, is_orchestrator: e.target.checked })}
                        className="accent-indigo-500"
                      />
                      <span className="text-sm text-zinc-300">Is Orchestrator (routes queries to other agents)</span>
                    </label>

                    {selected.is_orchestrator && (
                      <div className="block">
                        <span className="text-xs font-medium text-zinc-400">Routes To</span>
                        <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
                          {agents.length <= 1 && (
                            <p className="text-xs text-zinc-500">No other agents available.</p>
                          )}
                          {agents
                            .filter((a) => a.slug !== selected.slug)
                            .map((a) => {
                              const checked = (selected.routes_to || []).includes(a.slug);
                              return (
                                <label key={a.slug} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-900 rounded-md px-1 py-0.5 transition">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleRoute(selected, a.slug)}
                                    className="accent-indigo-500"
                                  />
                                  <span>{a.name || a.slug}</span>
                                  <span className="text-xs text-zinc-500">@{a.slug}</span>
                                </label>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "knowledge" && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <label className="block">
                        <span className="text-xs font-medium text-zinc-400">Retrieval Top-K (1-20)</span>
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
                          className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                        />
                        <p className="text-xs text-zinc-500 mt-1">
                          Number of chunks retrieved per query.
                        </p>
                      </label>
                    </div>

                    <div>
                      <h3 className="text-sm font-medium text-zinc-300 mb-1">Connected Knowledge Sources</h3>
                      <p className="text-xs text-zinc-500 mb-3">
                        Select the knowledge sources this agent can retrieve from. Retrieval is automatically enabled when at least one source is connected.
                      </p>
                      <div className="space-y-1 max-h-64 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
                        {sources.length === 0 && (
                          <p className="text-xs text-zinc-500">No sources configured. Go to Knowledge Sources to add documents.</p>
                        )}
                        {sources.map((s) => {
                          const checked = (selected.connected_sources || []).includes(s.id);
                          return (
                            <label key={s.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-900 rounded-md px-1 py-0.5 transition">
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
                                className="accent-indigo-500"
                              />
                              <span>{s.name}</span>
                              <span className="text-xs text-zinc-500">({s.slug})</span>
                            </label>
                          );
                        })}
                      </div>
                    </div>

                    {(selected.connected_sources || []).length > 0 && (
                      <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2">
                        <p className="text-xs text-indigo-300">
                          <strong>{(selected.connected_sources || []).length}</strong> source(s) connected. Retrieval is active.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "deploy" && (
                  <div className="space-y-4">
                    <label className="block">
                      <span className="text-xs font-medium text-zinc-400">Visibility</span>
                      <select
                        value={selected.visibility || "all"}
                        onChange={(e) => setSelected({ ...selected, visibility: e.target.value })}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                      >
                        <option value="all">All users</option>
                        <option value="admin_only">Admins only</option>
                        <option value="restricted">Restricted to specific users</option>
                      </select>
                    </label>

                    {selected.visibility === "restricted" && (
                      <div className="block">
                        <span className="text-xs font-medium text-zinc-400">Allowed Users</span>
                        <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
                          {users.length === 0 && (
                            <p className="text-xs text-zinc-500">No users found.</p>
                          )}
                          {users.map((u) => {
                            const checked = (selected.allowed_users || []).includes(u.email);
                            const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                            return (
                              <label key={u.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-900 rounded-md px-1 py-0.5 transition">
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => toggleAllowedUser(selected, u.email)}
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
                  </div>
                )}
              </div>

              </div>

              {/* Footer save */}
              <div className="flex justify-end px-5 py-4 border-t border-zinc-800">
                <button
                  onClick={save}
                  disabled={saving}
                  className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-500/15"
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {saving ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-zinc-500">
              <Bot className="h-10 w-10 text-zinc-700 mb-3" />
              <p className="text-sm">Select an agent to configure</p>
            </div>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center gap-2 pb-3 border-b border-zinc-800">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10">
                <Bot className="h-4 w-4 text-indigo-400" />
              </div>
              <h2 className="font-semibold text-lg">Create New Agent</h2>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Slug *</span>
                <input
                  value={newAgent.slug}
                  onChange={(e) => setNewAgent({ ...newAgent, slug: e.target.value })}
                  placeholder="e.g. finance"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                />
                <p className="text-xs text-zinc-500 mt-0.5">Unique identifier, no spaces.</p>
              </label>
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Name</span>
                <input
                  value={newAgent.name}
                  onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                  placeholder="e.g. Finance Specialist"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                />
              </label>
            </div>

            <label className="block">
              <span className="text-xs font-medium text-zinc-400">Description</span>
              <textarea
                value={newAgent.description}
                onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                rows={2}
                placeholder="What this agent does..."
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
              />
            </label>

            <label className="block">
              <span className="text-xs font-medium text-zinc-400">Owner</span>
              <select
                value={newAgent.created_by || ""}
                onChange={(e) => setNewAgent({ ...newAgent, created_by: e.target.value })}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
              >
                <option value="">Use current admin as owner ({currentUser?.email || "unknown"})</option>
                {users.map((u) => (
                  <option key={u.id} value={u.email}>
                    {formatUserLabel(u)} — {u.email}
                  </option>
                ))}
              </select>
              <p className="text-xs text-zinc-500 mt-1">
                Owner metadata only. All admins can manage every agent. If you want access restrictions, set Visibility to Restricted and include allowed users.
              </p>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-zinc-400">LLM Model</span>
              <select
                value={newAgent.llm_model || "gpt-5.4-nano"}
                onChange={(e) => setNewAgent({ ...newAgent, llm_model: e.target.value })}
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
                value={newAgent.system_prompt}
                onChange={(e) => setNewAgent({ ...newAgent, system_prompt: e.target.value })}
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
                      checked={(newAgent.tools || []).includes(tool)}
                      onChange={() => toggleTool(newAgent, tool)}
                      className="accent-indigo-500"
                    />
                    <span className="capitalize">{tool.replace(/_/g, " ")}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-zinc-500 mt-1.5">
                {(newAgent.connected_sources || []).length > 0
                  ? "Retrieval is enabled automatically because knowledge sources are connected."
                  : "Connect knowledge sources to enable retrieval."}
              </p>
            </div>

            <label className="block">
              <span className="text-xs font-medium text-zinc-400">Visibility</span>
              <select
                value={newAgent.visibility || "all"}
                onChange={(e) => setNewAgent({ ...newAgent, visibility: e.target.value })}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
              >
                <option value="all">All users</option>
                <option value="admin_only">Admins only</option>
                <option value="restricted">Restricted to specific users</option>
              </select>
            </label>

            {newAgent.visibility === "restricted" && (
              <div className="block">
                <span className="text-xs font-medium text-zinc-400">Allowed Users</span>
                <div className="mt-1 space-y-1 max-h-40 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
                  {users.length === 0 && (
                    <p className="text-xs text-zinc-500">No users found.</p>
                  )}
                  {users.map((u) => {
                    const checked = (newAgent.allowed_users || []).includes(u.email);
                    const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                    return (
                      <label key={u.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-800 rounded-md px-1 py-0.5 transition">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleAllowedUser(newAgent, u.email)}
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

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={newAgent.is_orchestrator}
                onChange={(e) => setNewAgent({ ...newAgent, is_orchestrator: e.target.checked })}
                className="accent-indigo-500"
              />
              <span className="text-sm text-zinc-300">Is Orchestrator (routes queries to other agents)</span>
            </label>

            {newAgent.is_orchestrator && (
              <div className="block">
                <span className="text-xs font-medium text-zinc-400">Routes To</span>
                <div className="mt-1 space-y-1 max-h-32 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2">
                  {agents.length === 0 && (
                    <p className="text-xs text-zinc-500">No other agents available.</p>
                  )}
                  {agents
                    .filter((a) => a.slug !== newAgent.slug)
                    .map((a) => {
                      const checked = (newAgent.routes_to || []).includes(a.slug);
                      return (
                        <label key={a.slug} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-800 rounded-md px-1 py-0.5 transition">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleRoute(newAgent, a.slug)}
                            className="accent-indigo-500"
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
                onClick={() => { setShowCreate(false); setError(null); }}
                className="px-4 py-2 rounded-lg text-sm bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition"
              >
                Cancel
              </button>
              <button
                onClick={create}
                disabled={creating}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-500/15"
              >
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                {creating ? "Creating…" : "Create Agent"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-500/10">
                <Trash2 className="h-5 w-5 text-red-400" />
              </div>
              <h2 className="font-semibold text-lg">Delete Agent?</h2>
            </div>
            <p className="text-sm text-zinc-400">
              Are you sure you want to delete <strong className="text-zinc-200">{deleteConfirm}</strong>? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-lg text-sm bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => remove(deleteConfirm)}
                className="bg-red-600 hover:bg-red-500 px-4 py-2 rounded-lg text-sm font-medium transition shadow-lg shadow-red-500/15"
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
