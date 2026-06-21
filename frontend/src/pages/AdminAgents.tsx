import { useEffect, useRef, useState, useCallback } from "react";
import { useLocation, useParams, useNavigate } from "react-router-dom";
import { Loader2, Plus, RefreshCw, Save, Trash2, Bot, Settings, BookOpen, Wrench, Rocket, Globe, ChevronLeft, ChevronDown, ChevronUp, Workflow, RotateCcw, History, AlertTriangle, Eye, EyeOff, ThumbsUp, X, MessageSquare, FileText, Activity } from "lucide-react";
import { api, type AgentSetting, type AgentSettingUpdate, type AgentSettingCreate, type KnowledgeSource, type DbUser, type AgentVersion, type AgentVersionDetail, type AgentPublishRequest, type MessageFeedback, type AgentFeedbackSummary, type AgentEvalTest, type AgentEvalRun, type AgentEvalRunDetail } from "@/lib/api";
import AgentIcon from "@/components/AgentIcon";
import AgentWorkflowEditor from "@/components/AgentWorkflowEditor";
import AgentListTable from "@/components/admin/agents/AgentListTable";
import CreateAgentPanel from "@/components/admin/agents/CreateAgentPanel";
import AdminPageHeader from "@/components/admin/AdminPageHeader";
import { useAuth } from "@/stores/auth";

type TabKey = "overview" | "tools" | "knowledge" | "agent-to-agent" | "deploy" | "versions" | "feedback" | "evaluation";

const ALL_TABS: { key: TabKey; label: string; icon: typeof Settings }[] = [
  { key: "overview", label: "Overview", icon: Settings },
  { key: "tools", label: "Tools", icon: Wrench },
  { key: "knowledge", label: "Knowledge", icon: BookOpen },
  { key: "agent-to-agent", label: "Agent-to-Agent", icon: Workflow },
  { key: "deploy", label: "Deploy", icon: Globe },
  { key: "versions", label: "Versions", icon: History },
  { key: "feedback", label: "Feedback", icon: ThumbsUp },
  { key: "evaluation", label: "Evaluation", icon: Activity },
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
  is_router: false,
  routes_to: [],
  visibility: "all",
  created_by: "",
  allow_uploads: true,
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

function diffWords(oldText: string, newText: string): { type: "same" | "del" | "ins"; text: string }[] {
  const oldWords = oldText.split(/(\s+)/).filter(Boolean);
  const newWords = newText.split(/(\s+)/).filter(Boolean);
  const m = oldWords.length;
  const n = newWords.length;
  const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = oldWords[i] === newWords[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const result: { type: "same" | "del" | "ins"; text: string }[] = [];
  let i = 0, j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && oldWords[i] === newWords[j]) {
      result.push({ type: "same", text: oldWords[i] });
      i++; j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({ type: "ins", text: newWords[j] });
      j++;
    } else if (i < m) {
      result.push({ type: "del", text: oldWords[i] });
      i++;
    } else {
      break;
    }
  }
  return result;
}

function resolveSourceNames(ids: string[] | null | undefined, sourceList: KnowledgeSource[]): string {
  if (!ids || ids.length === 0) return "—";
  return ids.map((id) => sourceList.find((s) => s.id === id)?.name || id).join(", ");
}

function mergeAgentDraft(agent: AgentSetting): AgentSetting {
  if (!agent.draft_config || Object.keys(agent.draft_config).length === 0) return agent;
  const draft = agent.draft_config;
  const merged: AgentSetting = { ...agent };
  if ("name" in draft) merged.name = draft.name as string | null;
  if ("description" in draft) merged.description = draft.description as string | null;
  if ("llm_model" in draft) merged.llm_model = draft.llm_model as string | null;
  if ("system_prompt" in draft) merged.system_prompt = draft.system_prompt as string | null;
  if ("retrieval_top_k" in draft) merged.retrieval_top_k = draft.retrieval_top_k as number;
  if ("connected_sources" in draft) merged.connected_sources = draft.connected_sources as string[] | null;
  if ("tools" in draft) merged.tools = draft.tools as string[] | null;
  if ("is_orchestrator" in draft) merged.is_orchestrator = draft.is_orchestrator as boolean;
  if ("routes_to" in draft) merged.routes_to = draft.routes_to as string[] | null;
  if ("visibility" in draft) merged.visibility = draft.visibility as string;
  if ("created_by" in draft) merged.created_by = draft.created_by as string | null;
  if ("allow_uploads" in draft) merged.allow_uploads = draft.allow_uploads as boolean;
  if ("allowed_users" in draft) merged.allowed_users = draft.allowed_users as string[] | null;
  if ("beta_users" in draft) merged.beta_users = draft.beta_users as string[] | null;
  if ("mode_profile" in draft) merged.mode_profile = draft.mode_profile as Record<string, unknown> | null;
  return merged;
}

const makeDefaultNewAgent = (ownerEmail = ""): AgentSettingCreate => ({
  ...DEFAULT_NEW_AGENT,
  created_by: ownerEmail,
});

export default function AdminAgents() {
  const { user: currentUser } = useAuth();
  const location = useLocation();
  const { agentSlug: urlAgentSlug } = useParams();
  const navigate = useNavigate();
  const didAutoOpen = useRef(false);
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
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [feedbackList, setFeedbackList] = useState<MessageFeedback[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<AgentFeedbackSummary | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [selectedFeedback, setSelectedFeedback] = useState<MessageFeedback | null>(null);
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<number>>(new Set());
  const toggleToolCall = (idx: number) => {
    setExpandedToolCalls((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());
  const toggleSource = (idx: number) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishNotes, setPublishNotes] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [versionDetail, setVersionDetail] = useState<AgentVersionDetail | null>(null);
  const [showTestDraft, setShowTestDraft] = useState(false);
  const [testDraftMessage, setTestDraftMessage] = useState("");
  const [testDraftResponse, setTestDraftResponse] = useState("");
  const [testingDraft, setTestingDraft] = useState(false);

  const [evalTests, setEvalTests] = useState<AgentEvalTest[]>([]);
  const [evalRuns, setEvalRuns] = useState<AgentEvalRun[]>([]);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalSubTab, setEvalSubTab] = useState<"tests" | "runs">("tests");
  const [showEvalTestModal, setShowEvalTestModal] = useState(false);
  const [editingEvalTest, setEditingEvalTest] = useState<AgentEvalTest | null>(null);
  const [evalTestForm, setEvalTestForm] = useState({ name: "", question: "", expected_answer: "" });
  const [showLaunchRunModal, setShowLaunchRunModal] = useState(false);
  const [launchRunForm, setLaunchRunForm] = useState<{
    name: string;
    thresholds: Record<string, number>;
    selectedTestIds: Set<string>;
  }>({
    name: "",
    thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
    selectedTestIds: new Set<string>(),
  });
  const [selectedEvalRun, setSelectedEvalRun] = useState<AgentEvalRunDetail | null>(null);
  const [selectedContext, setSelectedContext] = useState<string | null>(null);

  const closeSelected = () => {
    setSelected(null);
    setActiveTab("overview");
    navigate("/admin/agents");
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
      const mergedAgents = agentData.map(mergeAgentDraft);
      setAgents(mergedAgents);
      setSources(sourceData);
      setUsers(userData);
      setModels(modelData);

      // auto-select from URL slug
      if (urlAgentSlug && !didAutoOpen.current) {
        const target = mergedAgents.find((a) => a.slug === urlAgentSlug) ?? null;
        if (target) {
          didAutoOpen.current = true;
          setSelected(target);
          setActiveTab("overview");
        }
      }
      // auto-select from template gallery redirect
      else {
        const state = location.state as { selectedSlug?: string } | null;
        if (state?.selectedSlug) {
          const target = mergedAgents.find((a) => a.slug === state.selectedSlug) ?? null;
          if (target) {
            setSelected(target);
            // clear state so it doesn't re-select on manual refresh
            window.history.replaceState({}, document.title);
          }
        } else if (selected) {
          const updated = mergedAgents.find((a) => a.slug === selected.slug) ?? null;
          setSelected(updated);
        }
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

  // Load versions when agent is selected or versions tab is active
  const loadVersions = useCallback(async (slug: string) => {
    try {
      const data = await api.listAgentVersions(slug);
      setVersions(data);
    } catch {
      setVersions([]);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "versions") {
      loadVersions(selected.slug);
    }
  }, [selected, activeTab, loadVersions]);

  const loadFeedback = useCallback(async (slug: string) => {
    setFeedbackLoading(true);
    try {
      const [list, summary] = await Promise.all([
        api.getAgentFeedback(slug, { limit: 100 }),
        api.getAgentFeedbackSummary(slug),
      ]);
      setFeedbackList(list);
      setFeedbackSummary(summary);
    } catch {
      setFeedbackList([]);
      setFeedbackSummary(null);
    } finally {
      setFeedbackLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "feedback") {
      loadFeedback(selected.slug);
    }
  }, [selected, activeTab, loadFeedback]);

  const loadEvalData = useCallback(async (slug: string) => {
    setEvalLoading(true);
    try {
      const [tests, runs] = await Promise.all([
        api.listEvalTests(slug),
        api.listEvalRuns(slug),
      ]);
      setEvalTests(tests);
      setEvalRuns(runs);
    } catch {
      setEvalTests([]);
      setEvalRuns([]);
    } finally {
      setEvalLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "evaluation") {
      loadEvalData(selected.slug);
    }
  }, [selected, activeTab, loadEvalData]);


  const hasDraftChanges = (agent: AgentSetting | null): boolean => {
    if (!agent) return false;
    if (!agent.is_published) return false;
    return agent.draft_config !== null && Object.keys(agent.draft_config).length > 0;
  };

  const handlePublish = async () => {
    if (!selected) return;
    setPublishing(true);
    setError(null);
    try {
      const body: AgentPublishRequest = { notes: publishNotes || null };
      const updated = await api.publishAgent(selected.slug, body);
      setSelected(updated);
      setShowPublishModal(false);
      setPublishNotes("");
            await refresh();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setPublishing(false);
    }
  };

  const handleDiscardDraft = async () => {
    if (!selected) return;
    setError(null);
    try {
      const updated = await api.discardAgentDraft(selected.slug);
      setSelected(updated);
            await refresh();
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    }
  };

  const handleRestoreVersion = async (versionId: string) => {
    if (!selected) return;
    setRestoring(true);
    setError(null);
    try {
      const updated = await api.restoreAgentVersion(selected.slug, versionId);
      setSelected(updated);
      await refresh();
      await loadVersions(selected.slug);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setRestoring(false);
    }
  };

  const handleViewVersion = async (versionId: string) => {
    if (!selected) return;
    try {
      const detail = await api.getAgentVersion(selected.slug, versionId);
      setVersionDetail(detail);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    }
  };

  const handleTestDraft = async () => {
    if (!selected || !testDraftMessage.trim()) return;
    setTestingDraft(true);
    setError(null);
    try {
      const res = await api.testAgentDraft(selected.slug, { content: testDraftMessage });
      setTestDraftResponse(res.response);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setTestingDraft(false);
    }
  };

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
        allow_uploads: selected.allow_uploads !== false,
        allowed_users: selected.allowed_users || undefined,
        beta_users: selected.beta_users || undefined,
        agent_type: selected.agent_type || "standard",
        research_config: selected.research_config || undefined,
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
        allow_uploads: newAgent.allow_uploads !== false,
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
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <AdminPageHeader
        title="Agents"
        description="Configure and manage AI agents for your workspace"
        icon={Bot}
      >
        <button
          onClick={() => { setShowCreate(true); setError(null); setNewAgent(makeDefaultNewAgent(currentUser?.email || "")); }}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-3 py-2 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
        >
          <Plus className="h-3.5 w-3.5" />
          Create Agent
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {error && (
        <div className="mb-4 bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Agents table */}
        <div className={selected ? "hidden" : "w-full"}>
          <AgentListTable
            agents={agents}
            users={users}
            loading={loading}
            selectedSlug={selected?.slug ?? null}
            onSelect={(slug: string) => {
              const a = agents.find((ag) => ag.slug === slug);
              if (a) {
                setSelected(a);
                setActiveTab("overview");
                navigate(`/admin/agents/${slug}`);
              }
            }}
            onDelete={(slug: string) => setDeleteConfirm(slug)}
          />
        </div>

        {/* Detail panel */}
        <div className={selected ? "flex-1 min-w-0 h-full" : "hidden"}>
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
                      <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-zinc-100">{selected.name || selected.slug}</h2>
                        {/* Status badge */}
                        {selected.is_published ? (
                          hasDraftChanges(selected) ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/20">
                              <AlertTriangle className="h-3 w-3" />
                              Modified
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
                              <Eye className="h-3 w-3" />
                              Published
                            </span>
                          )
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-zinc-700/30 px-2 py-0.5 text-[11px] font-medium text-zinc-400 border border-zinc-700/50">
                            <EyeOff className="h-3 w-3" />
                            Draft
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-zinc-500 uppercase tracking-wide">{selected.slug}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {selected.is_published && hasDraftChanges(selected) && (
                    <>
                      <button
                        onClick={() => { setShowTestDraft(true); setTestDraftMessage(""); setTestDraftResponse(""); }}
                        className="flex items-center gap-1.5 text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 px-3 py-2 rounded-lg transition"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        Test Draft
                      </button>
                      <button
                        onClick={handleDiscardDraft}
                        className="flex items-center gap-1.5 text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 px-3 py-2 rounded-lg transition"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Discard
                      </button>
                      <button
                        onClick={() => setShowPublishModal(true)}
                        className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-3 py-2 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
                      >
                        <Rocket className="h-3.5 w-3.5" />
                        Publish
                      </button>
                    </>
                  )}
                  {!selected.is_published && (
                    <button
                      onClick={() => setShowPublishModal(true)}
                      className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-3 py-2 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
                    >
                      <Rocket className="h-3.5 w-3.5" />
                      Publish
                    </button>
                  )}
                </div>
              </div>

              <div className="flex flex-1 min-h-0">
                <div className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-950/40 p-3 h-full overflow-y-auto">
                  <div className="mb-3 px-2 text-[11px] font-medium uppercase tracking-wide text-zinc-500">
                    Sections
                  </div>
                  <div className="space-y-1">
                    {(selected.agent_type === "deep_research"
                      ? ALL_TABS.filter((t) => ["overview", "knowledge", "deploy", "versions", "feedback"].includes(t.key))
                      : ALL_TABS
                    ).map((t) => {
                      const Icon = t.icon;
                      const active = activeTab === t.key;
                      return (
                        <button
                          key={t.key}
                          onClick={() => {
                            setActiveTab(t.key);
                          }}
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

                    {/* Agent Type Selector */}
                    <label className="block">
                      <span className="text-xs font-medium text-zinc-400">Agent Type</span>
                      <select
                        value={selected.agent_type || "standard"}
                        onChange={(e) => {
                          const newType = e.target.value;
                          const updates: Partial<AgentSetting> = { agent_type: newType };
                          if (newType === "deep_research" && !selected.research_config) {
                            updates.research_config = {
                              max_researcher_iterations: 5,
                              max_concurrent_research_units: 3,
                              max_react_tool_calls: 8,
                              clarification_model: "gpt-5.4-nano",
                              research_model: "gpt-5.4",
                              compression_model: "gpt-5.4",
                              final_report_model: "gpt-5.4",
                              search_tools: ["web_search"],
                              connected_sources: [],
                            };
                            updates.tools = ["web_search"];
                            updates.web_search_enabled = true;
                            updates.is_orchestrator = false;
                            updates.is_router = false;
                            updates.routes_to = [];
                          }
                          setSelected({ ...selected, ...updates });
                        }}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                      >
                        <option value="standard">Standard Agent</option>
                        <option value="deep_research">Deep Research Agent</option>
                      </select>
                    </label>

                    {/* Deep Research Config Panel */}
                    {selected.agent_type === "deep_research" && selected.research_config && (
                      <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-4 space-y-4">
                        <div className="flex items-center gap-2 text-sm font-medium text-indigo-300">
                          <Workflow className="h-4 w-4" />
                          Deep Research Configuration
                        </div>

                        {/* Search Tools */}
                        <div>
                          <span className="text-xs font-medium text-zinc-400">Search Tools</span>
                          <div className="mt-2 flex flex-wrap gap-3">
                            <label className="flex items-center gap-1.5 text-sm text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={selected.research_config.search_tools.includes("web_search")}
                                onChange={() => {
                                  const rc = { ...selected.research_config! };
                                  const has = rc.search_tools.includes("web_search");
                                  rc.search_tools = has
                                    ? rc.search_tools.filter((t) => t !== "web_search")
                                    : [...rc.search_tools, "web_search"];
                                  setSelected({ ...selected, research_config: rc });
                                }}
                                className="accent-indigo-500"
                              />
                              <span>Web Search (Tavily)</span>
                            </label>
                            <label className="flex items-center gap-1.5 text-sm text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={selected.research_config.search_tools.includes("retrieve")}
                                onChange={() => {
                                  const rc = { ...selected.research_config! };
                                  const has = rc.search_tools.includes("retrieve");
                                  rc.search_tools = has
                                    ? rc.search_tools.filter((t) => t !== "retrieve")
                                    : [...rc.search_tools, "retrieve"];
                                  setSelected({ ...selected, research_config: rc });
                                }}
                                className="accent-indigo-500"
                              />
                              <span>Internal Knowledge Base</span>
                            </label>
                          </div>
                        </div>

                        {/* Sliders */}
                        <div className="grid grid-cols-3 gap-4">
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Max Research Iterations</span>
                            <input
                              type="number"
                              min={1}
                              max={10}
                              value={selected.research_config.max_researcher_iterations}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, max_researcher_iterations: parseInt(e.target.value) || 5 };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            />
                          </label>
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Max Concurrent Researchers</span>
                            <input
                              type="number"
                              min={1}
                              max={10}
                              value={selected.research_config.max_concurrent_research_units}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, max_concurrent_research_units: parseInt(e.target.value) || 3 };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            />
                          </label>
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Max Tool Calls / Researcher</span>
                            <input
                              type="number"
                              min={1}
                              max={20}
                              value={selected.research_config.max_react_tool_calls}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, max_react_tool_calls: parseInt(e.target.value) || 8 };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            />
                          </label>
                        </div>

                        {/* Model Roles */}
                        <div className="grid grid-cols-2 gap-4">
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Clarification Model</span>
                            <select
                              value={selected.research_config.clarification_model}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, clarification_model: e.target.value };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            >
                              {models.map((m) => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </label>
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Research Model</span>
                            <select
                              value={selected.research_config.research_model}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, research_model: e.target.value };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            >
                              {models.map((m) => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </label>
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Compression Model</span>
                            <select
                              value={selected.research_config.compression_model}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, compression_model: e.target.value };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            >
                              {models.map((m) => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </label>
                          <label className="block">
                            <span className="text-xs font-medium text-zinc-400">Final Report Model</span>
                            <select
                              value={selected.research_config.final_report_model}
                              onChange={(e) => {
                                const rc = { ...selected.research_config!, final_report_model: e.target.value };
                                setSelected({ ...selected, research_config: rc });
                              }}
                              className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                            >
                              {models.map((m) => <option key={m} value={m}>{m}</option>)}
                            </select>
                          </label>
                        </div>
                      </div>
                    )}

                    {selected.agent_type !== "deep_research" && (
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
                    )}

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

                    <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={selected.allow_uploads !== false}
                        onChange={(e) => setSelected({ ...selected, allow_uploads: e.target.checked })}
                        className="accent-indigo-500"
                      />
                      <span>
                        <span className="block text-sm font-medium text-zinc-200">Allow file uploads</span>
                        <span className="block text-xs text-zinc-500">
                          Shows the attach button in chat when this agent is selected.
                        </span>
                      </span>
                    </label>

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

                    {/* Beta Testers */}
                    <div className="block">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-zinc-400">Beta Testers</span>
                        {(selected.beta_users || []).length > 0 && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/20">
                            Staged
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mb-1">
                        When beta testers are selected, only these users (and admins) can see the agent. Clear the list to release to all permitted users.
                      </p>
                      <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
                        {users.length === 0 && (
                          <p className="text-xs text-zinc-500">No users found.</p>
                        )}
                        {users.map((u) => {
                          const checked = (selected.beta_users || []).includes(u.email);
                          const display = [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;
                          return (
                            <label key={u.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-900 rounded-md px-1 py-0.5 transition">
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  const current = selected.beta_users || [];
                                  const next = checked
                                    ? current.filter((e) => e !== u.email)
                                    : [...current, u.email];
                                  setSelected({ ...selected, beta_users: next });
                                }}
                                className="accent-indigo-500"
                              />
                              <span>{display}</span>
                              <span className="text-xs text-zinc-500">{u.email}</span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === "agent-to-agent" && (
                  <div className="space-y-6">
                    {/* Routing */}
                    <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={selected.is_router || false}
                        onChange={(e) => setSelected({ ...selected, is_router: e.target.checked, is_orchestrator: false })}
                        className="accent-amber-500"
                      />
                      <span>
                        <span className="block text-sm font-medium text-zinc-200">Enable Routing</span>
                        <span className="block text-xs text-zinc-500">
                          This agent classifies user intent and routes the conversation to a single specialist agent.
                        </span>
                      </span>
                    </label>

                    {selected.is_router && (
                      <div className="block">
                        <span className="text-xs font-medium text-zinc-400">Routes To (Specialist Agents)</span>
                        <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
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
                                    className="accent-amber-500"
                                  />
                                  <span>{a.name || a.slug}</span>
                                  <span className="text-xs text-zinc-500">@{a.slug}</span>
                                </label>
                              );
                            })}
                          {agents.length <= 1 && (
                            <p className="text-xs text-zinc-500">No other agents available to route to.</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Orchestration */}
                    <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2.5">
                      <input
                        type="checkbox"
                        checked={selected.is_orchestrator || false}
                        onChange={(e) => setSelected({ ...selected, is_orchestrator: e.target.checked, is_router: false })}
                        className="accent-violet-500"
                      />
                      <span>
                        <span className="block text-sm font-medium text-zinc-200">Enable Orchestration</span>
                        <span className="block text-xs text-zinc-500">
                          This agent acts as a supervisor. It can call multiple child agents and synthesize their outputs into a final answer.
                        </span>
                      </span>
                    </label>

                    {selected.is_orchestrator && (
                      <div className="block">
                        <span className="text-xs font-medium text-zinc-400">Child Agents</span>
                        <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2">
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
                                    className="accent-violet-500"
                                  />
                                  <span>{a.name || a.slug}</span>
                                  <span className="text-xs text-zinc-500">@{a.slug}</span>
                                </label>
                              );
                            })}
                          {agents.length <= 1 && (
                            <p className="text-xs text-zinc-500">No other agents available.</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Workflows */}
                    <div className="border-t border-zinc-800 pt-4">
                      <h3 className="text-sm font-medium text-zinc-300 mb-1">Workflows</h3>
                      <p className="text-xs text-zinc-500 mb-3">
                        Define step-by-step DAG pipelines for this agent. Click a workflow or create a new one to open the diagram builder.
                      </p>
                      <AgentWorkflowEditor agentSlug={selected.slug} agents={agents} />
                    </div>
                  </div>
                )}

                {activeTab === "versions" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-zinc-200">Version History</h3>
                      {restoring && <Loader2 className="h-4 w-4 animate-spin text-zinc-500" />}
                    </div>

                    {versions.length === 0 ? (
                      <div className="text-center py-10">
                        <History className="mx-auto h-8 w-8 text-zinc-700 mb-2" />
                        <p className="text-sm text-zinc-500">No versions yet.</p>
                        <p className="text-xs text-zinc-600 mt-1">Publish this agent to create the first version.</p>
                      </div>
                    ) : (
                      <div className="rounded-lg border border-zinc-800 overflow-hidden">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-zinc-950/60 text-xs uppercase tracking-wide text-zinc-500">
                            <tr>
                              <th className="px-4 py-2 font-medium">Version</th>
                              <th className="px-4 py-2 font-medium">Date</th>
                              <th className="px-4 py-2 font-medium">Author</th>
                              <th className="px-4 py-2 font-medium">Notes</th>
                              <th className="px-4 py-2 font-medium text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800 bg-zinc-900">
                            {versions.map((v) => (
                              <tr key={v.id} className="hover:bg-zinc-800/30 transition">
                                <td className="px-4 py-2.5 font-mono text-xs text-zinc-300">
                                  <button
                                    onClick={() => handleViewVersion(v.id)}
                                    className="hover:text-indigo-400 transition"
                                  >
                                    v{v.version_number}
                                  </button>
                                </td>
                                <td className="px-4 py-2.5 text-zinc-400">{formatDateTime(v.created_at)}</td>
                                <td className="px-4 py-2.5 text-zinc-400">{v.created_by || "—"}</td>
                                <td className="px-4 py-2.5 text-zinc-400 max-w-xs truncate">{v.notes || "—"}</td>
                                <td className="px-4 py-2.5 text-right">
                                  <button
                                    onClick={() => handleViewVersion(v.id)}
                                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100 transition mr-2"
                                  >
                                    <Eye className="h-3 w-3" />
                                    View
                                  </button>
                                  <button
                                    onClick={() => handleRestoreVersion(v.id)}
                                    disabled={restoring}
                                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800 hover:text-zinc-100 transition disabled:opacity-40"
                                  >
                                    <RotateCcw className="h-3 w-3" />
                                    Restore
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {activeTab === "feedback" && (
                  <div className="space-y-6">
                    {/* Analytics cards */}
                    {feedbackSummary && (
                      <div className="grid grid-cols-4 gap-4">
                        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                          <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Total</div>
                          <div className="mt-1 text-2xl font-bold text-zinc-200">{feedbackSummary.total}</div>
                        </div>
                        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
                          <div className="text-xs font-medium text-emerald-500 uppercase tracking-wide">Thumbs Up</div>
                          <div className="mt-1 text-2xl font-bold text-emerald-400">{feedbackSummary.thumbs_up}</div>
                        </div>
                        <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4">
                          <div className="text-xs font-medium text-rose-500 uppercase tracking-wide">Thumbs Down</div>
                          <div className="mt-1 text-2xl font-bold text-rose-400">{feedbackSummary.thumbs_down}</div>
                        </div>
                        <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-4">
                          <div className="text-xs font-medium text-zinc-500 uppercase tracking-wide">Positive Rate</div>
                          <div className="mt-1 text-2xl font-bold text-zinc-200">{feedbackSummary.up_rate_pct}%</div>
                        </div>
                      </div>
                    )}

                    {/* Feedback table */}
                    {feedbackLoading ? (
                      <div className="flex items-center justify-center py-12">
                        <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
                      </div>
                    ) : feedbackList.length === 0 ? (
                      <div className="rounded-lg border border-zinc-800 bg-zinc-950/30 px-6 py-8 text-center">
                        <p className="text-sm text-zinc-500">No feedback yet for this agent.</p>
                      </div>
                    ) : (
                      <div className="rounded-lg border border-zinc-800 overflow-hidden">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-zinc-950/60 text-xs uppercase tracking-wide text-zinc-500">
                            <tr>
                              <th className="px-4 py-2 font-medium">Date</th>
                              <th className="px-4 py-2 font-medium">User</th>
                              <th className="px-4 py-2 font-medium">Rating</th>
                              <th className="px-4 py-2 font-medium">Comment</th>
                              <th className="px-4 py-2 font-medium">Screenshot</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-zinc-800">
                            {feedbackList.map((f) => (
                              <tr key={f.id} className="hover:bg-zinc-800/30 transition cursor-pointer" onClick={() => setSelectedFeedback(f)}>
                                <td className="px-4 py-2.5 text-zinc-400 whitespace-nowrap">
                                  {new Date(f.created_at).toLocaleString()}
                                </td>
                                <td className="px-4 py-2.5 text-zinc-400">{f.user_id.slice(0, 8)}…</td>
                                <td className="px-4 py-2.5">
                                  {f.thumbs_up ? (
                                    <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-400">
                                      <ThumbsUp className="h-3 w-3" /> Up
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 rounded-md bg-rose-500/10 px-2 py-0.5 text-xs text-rose-400">
                                      <ThumbsUp className="h-3 w-3" /> Down
                                    </span>
                                  )}
                                </td>
                                <td className="px-4 py-2.5 text-zinc-400 max-w-xs truncate">
                                  {f.comment || "—"}
                                </td>
                                <td className="px-4 py-2.5">
                                  {f.screenshot_attachment_id ? (
                                    <span className="text-xs text-indigo-400">Yes</span>
                                  ) : (
                                    <span className="text-xs text-zinc-600">No</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Evaluation */}
                {activeTab === "evaluation" && (
                  <div className="w-full space-y-6">
                  {/* Sub-tabs */}
                  <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
                    <button
                      onClick={() => setEvalSubTab("tests")}
                      className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "tests" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
                    >
                      Tests
                    </button>
                    <button
                      onClick={() => setEvalSubTab("runs")}
                      className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "runs" ? "bg-zinc-800 text-zinc-200" : "text-zinc-500 hover:text-zinc-300"}`}
                    >
                      Runs
                    </button>
                  </div>

                  {evalLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
                    </div>
                  ) : evalSubTab === "tests" ? (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium text-zinc-300">Evaluation Tests ({evalTests.length})</h3>
                        <button
                          onClick={() => {
                                                        setEditingEvalTest(null);
                            setEvalTestForm({ name: "", question: "", expected_answer: "" });
                            setShowEvalTestModal(true);
                          }}
                          className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-3 py-1.5 rounded-lg text-xs font-medium transition"
                        >
                          <Plus className="h-3.5 w-3.5" /> New Test
                        </button>
                      </div>
                      {evalTests.length === 0 ? (
                        <div className="rounded-lg border border-zinc-800 bg-zinc-950/30 px-6 py-8 text-center">
                          <p className="text-sm text-zinc-500">No evaluation tests yet.</p>
                          <p className="text-xs text-zinc-600 mt-1">Create tests with a question and expected answer to evaluate your agent.</p>
                        </div>
                      ) : (
                        <div className="rounded-lg border border-zinc-800 overflow-hidden">
                          <table className="min-w-full text-left text-sm">
                            <thead className="bg-zinc-950/60 text-xs uppercase tracking-wide text-zinc-500">
                              <tr>
                                <th className="px-4 py-2 font-medium">Name</th>
                                <th className="px-4 py-2 font-medium">Question</th>
                                <th className="px-4 py-2 font-medium">Expected Answer</th>
                                <th className="px-4 py-2 font-medium w-24"></th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800">
                              {evalTests.map((t) => (
                                <tr key={t.id} className="hover:bg-zinc-800/30 transition">
                                  <td className="px-4 py-2.5 text-zinc-300 font-medium">{t.name}</td>
                                  <td className="px-4 py-2.5 text-zinc-400 max-w-xs truncate">{t.question}</td>
                                  <td className="px-4 py-2.5 text-zinc-400 max-w-xs truncate">{t.expected_answer}</td>
                                  <td className="px-4 py-2.5">
                                    <div className="flex items-center gap-2">
                                      <button
                                        onClick={() => {
                                                                                    setEditingEvalTest(t);
                                          setEvalTestForm({ name: t.name, question: t.question, expected_answer: t.expected_answer });
                                          setShowEvalTestModal(true);
                                        }}
                                        className="text-zinc-500 hover:text-zinc-300 transition"
                                        title="Edit"
                                      >
                                        <Settings className="h-3.5 w-3.5" />
                                      </button>
                                      <button
                                        onClick={async () => {
                                          if (!selected) return;
                                          if (!confirm("Delete this test?")) return;
                                                                                    try {
                                            await api.deleteEvalTest(selected.slug, t.id);
                                            loadEvalData(selected.slug);
                                            // Re-sync selected agent to prevent stale status
                                            try {
                                              const agents = await api.listAgentSettings();
                                              const updated = agents.find((a) => a.slug === selected.slug);
                                              if (updated) setSelected(updated);
                                            } catch { /* ignore */ }
                                          } catch {
                                            alert("Failed to delete test");
                                          }
                                        }}
                                        className="text-zinc-500 hover:text-rose-400 transition"
                                        title="Delete"
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium text-zinc-300">Evaluation Runs ({evalRuns.length})</h3>
                        <button
                          onClick={() => {
                                                        setLaunchRunForm({
                              name: `Run ${new Date().toLocaleString()}`,
                              thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
                              selectedTestIds: new Set(evalTests.map((t) => t.id)),
                            });
                            setShowLaunchRunModal(true);
                          }}
                          disabled={evalTests.length === 0}
                          className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg text-xs font-medium transition"
                        >
                          <Rocket className="h-3.5 w-3.5" /> Launch Run
                        </button>
                      </div>
                      {evalRuns.length === 0 ? (
                        <div className="rounded-lg border border-zinc-800 bg-zinc-950/30 px-6 py-8 text-center">
                          <p className="text-sm text-zinc-500">No evaluation runs yet.</p>
                          <p className="text-xs text-zinc-600 mt-1">Launch a run to evaluate your agent against the test cases.</p>
                        </div>
                      ) : (
                        <div className="rounded-lg border border-zinc-800 overflow-hidden">
                          <table className="min-w-full text-left text-sm">
                            <thead className="bg-zinc-950/60 text-xs uppercase tracking-wide text-zinc-500">
                              <tr>
                                <th className="px-4 py-2 font-medium">Name</th>
                                <th className="px-4 py-2 font-medium">Status</th>
                                <th className="px-4 py-2 font-medium">Pass Rate</th>
                                <th className="px-4 py-2 font-medium">Date</th>
                                <th className="px-4 py-2 font-medium w-24"></th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-zinc-800">
                              {evalRuns.map((r) => (
                                <tr key={r.id} className="hover:bg-zinc-800/30 transition cursor-pointer" onClick={async () => {
                                  if (!selected) return;
                                  try {
                                    const detail = await api.getEvalRunDetail(selected.slug, r.id);
                                    setSelectedEvalRun(detail);
                                  } catch {
                                    alert("Failed to load run details");
                                  }
                                }}>
                                  <td className="px-4 py-2.5 text-zinc-300 font-medium">{r.name}</td>
                                  <td className="px-4 py-2.5">
                                    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${
                                      r.status === "completed" ? "bg-emerald-500/10 text-emerald-400" :
                                      r.status === "running" ? "bg-amber-500/10 text-amber-400" :
                                      r.status === "failed" ? "bg-rose-500/10 text-rose-400" :
                                      "bg-zinc-500/10 text-zinc-400"
                                    }`}>
                                      {r.status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
                                      {r.status}
                                    </span>
                                  </td>
                                  <td className="px-4 py-2.5">
                                    {r.total_tests > 0 ? (
                                      <div className="flex items-center gap-2">
                                        <div className="w-20 h-2 bg-zinc-800 rounded-full overflow-hidden">
                                          <div
                                            className="h-full bg-emerald-500 rounded-full"
                                            style={{ width: `${(r.pass_count / r.total_tests) * 100}%` }}
                                          />
                                        </div>
                                        <span className="text-xs text-zinc-400">{r.pass_count}/{r.total_tests}</span>
                                      </div>
                                    ) : (
                                      <span className="text-xs text-zinc-600">—</span>
                                    )}
                                  </td>
                                  <td className="px-4 py-2.5 text-zinc-400 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                                  <td className="px-4 py-2.5">
                                    <button
                                      onClick={async (e) => {
                                        e.stopPropagation();
                                        if (!selected) return;
                                        if (!confirm("Delete this run?")) return;
                                                                                try {
                                          await api.deleteEvalRun(selected.slug, r.id);
                                          loadEvalData(selected.slug);
                                          // Re-sync selected agent to prevent stale status
                                          try {
                                            const agents = await api.listAgentSettings();
                                            const updated = agents.find((a) => a.slug === selected.slug);
                                            if (updated) setSelected(updated);
                                          } catch { /* ignore */ }
                                        } catch {
                                          alert("Failed to delete run");
                                        }
                                      }}
                                      className="text-zinc-500 hover:text-rose-400 transition"
                                      title="Delete"
                                    >
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
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
                  className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-500/15"
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

      <CreateAgentPanel
        open={showCreate}
        onClose={() => { setShowCreate(false); setError(null); }}
        agent={newAgent}
        onChange={setNewAgent}
        onCreate={create}
        creating={creating}
        users={users}
        models={models}
        agents={agents}
        currentUserEmail={currentUser?.email}
        error={error}
        onClearError={() => setError(null)}
      />

      {/* Delete confirmation */}
      {deleteConfirm && (
        <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="animate-scale-in bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
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
                className="px-4 py-2 rounded-lg text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 transition"
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

      {/* Publish modal */}
      {showPublishModal && selected && (
        <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="animate-scale-in bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-500/10">
                <Rocket className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <h2 className="font-semibold text-lg">
                  {selected.is_published ? "Publish Changes" : "Publish Agent"}
                </h2>
                <p className="text-xs text-zinc-500">
                  {selected.is_published
                    ? "This will snapshot the current live config and apply your draft changes."
                    : "This will make the agent visible to all permitted users."}
                </p>
              </div>
            </div>

            <label className="block">
              <span className="text-xs font-medium text-zinc-400">Notes (optional)</span>
              <textarea
                value={publishNotes}
                onChange={(e) => setPublishNotes(e.target.value)}
                placeholder="What changed in this version?"
                rows={2}
                className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
              />
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => { setShowPublishModal(false); setPublishNotes(""); }}
                className="px-4 py-2 rounded-lg text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 transition"
              >
                Cancel
              </button>
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition shadow-lg shadow-indigo-500/15"
              >
                {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                {publishing ? "Publishing…" : "Publish"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Version diff modal */}
      {versionDetail && selected && (
        <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-2xl space-y-4 shadow-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-lg">
                  Version v{versionDetail.version_number}
                </h2>
                <p className="text-xs text-zinc-500">
                  {versionDetail.notes || "No notes"} · {formatDateTime(versionDetail.created_at)}
                </p>
              </div>
              <button
                onClick={() => setVersionDetail(null)}
                className="text-zinc-500 hover:text-zinc-300 transition"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3">
              {(() => {
                const config = versionDetail.config as Record<string, unknown>;
                const live = selected;
                const fields = [
                  { key: "name", label: "Name" },
                  { key: "description", label: "Description", textDiff: true },
                  { key: "llm_model", label: "LLM Model" },
                  { key: "system_prompt", label: "System Prompt", textDiff: true },
                  { key: "connected_sources", label: "Knowledge Sources", sourceNames: true },
                  { key: "tools", label: "Tools" },
                  { key: "is_orchestrator", label: "Orchestrator" },
                  { key: "routes_to", label: "Routes To" },
                  { key: "visibility", label: "Visibility" },
                ];
                return fields.map(({ key, label, textDiff, sourceNames }) => {
                  let vVal: unknown = config[key] ?? "—";
                  let lVal: unknown = (live as unknown as Record<string, unknown>)[key] ?? "—";

                  if (sourceNames && key === "connected_sources") {
                    vVal = resolveSourceNames(vVal as string[] | null | undefined, sources);
                    lVal = resolveSourceNames(lVal as string[] | null | undefined, sources);
                  }

                  const changed = JSON.stringify(vVal) !== JSON.stringify(lVal);
                  const oldText = typeof vVal === "string" ? vVal : JSON.stringify(vVal);
                  const newText = typeof lVal === "string" ? lVal : JSON.stringify(lVal);

                  return (
                    <div key={key} className={`rounded-lg border px-3 py-2 text-sm ${changed ? "border-amber-500/30 bg-amber-500/5" : "border-zinc-800 bg-zinc-900/50"}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-zinc-300">{label}</span>
                        {changed && <span className="text-[10px] font-medium text-amber-400 uppercase tracking-wide">Changed</span>}
                      </div>
                      {textDiff && changed ? (
                        <div className="text-xs leading-relaxed">
                          {diffWords(oldText, newText).map((seg, idx) => (
                            <span
                              key={idx}
                              className={
                                seg.type === "del"
                                  ? "bg-red-500/20 text-red-300 line-through decoration-red-400 px-0.5 rounded"
                                  : seg.type === "ins"
                                  ? "bg-emerald-500/20 text-emerald-300 px-0.5 rounded"
                                  : "text-zinc-400"
                              }
                            >
                              {seg.text}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div>
                            <span className="text-zinc-500 block mb-0.5">Version</span>
                            <span className="text-zinc-400 font-mono break-all">{oldText}</span>
                          </div>
                          <div>
                            <span className="text-zinc-500 block mb-0.5">Current Live</span>
                            <span className="text-zinc-400 font-mono break-all">{newText}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                });
              })()}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button
                onClick={() => setVersionDetail(null)}
                className="px-4 py-2 rounded-lg text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Feedback detail modal */}
      {selectedFeedback && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => setSelectedFeedback(null)}>
          <div
            className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
              <div className="flex items-center gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${selectedFeedback.thumbs_up ? "bg-emerald-500/10" : "bg-rose-500/10"}`}>
                  <ThumbsUp className={`h-4 w-4 ${selectedFeedback.thumbs_up ? "text-emerald-400" : "text-rose-400"}`} />
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-zinc-200">
                    {selectedFeedback.thumbs_up ? "Thumbs Up" : "Thumbs Down"} — {selectedFeedback.user_id.slice(0, 8)}…
                  </h3>
                  <p className="text-xs text-zinc-500">{new Date(selectedFeedback.created_at).toLocaleString()}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedFeedback(null)}
                className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-5 space-y-6">
              {/* Comment */}
              {selectedFeedback.comment && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <MessageSquare className="h-3.5 w-3.5" />
                    User Comment
                  </div>
                  <div className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm text-zinc-300">
                    {selectedFeedback.comment}
                  </div>
                </div>
              )}

              {/* Conversation Actions */}
              {selectedFeedback.conversation_actions && selectedFeedback.conversation_actions.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <Rocket className="h-3.5 w-3.5" />
                    Conversation Actions ({selectedFeedback.conversation_actions.length})
                  </div>
                  <div className="space-y-2">
                    {selectedFeedback.conversation_actions.map((action, i) => (
                      <div key={i} className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 rounded px-1.5 py-0.5 uppercase tracking-wide">
                            {action.type.replace(/_/g, " ")}
                          </span>
                          {action.ticket_key && (
                            <a
                              href={action.ticket_url || "#"}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {action.ticket_key}
                            </a>
                          )}
                        </div>
                        {action.summary && (
                          <p className="text-xs text-zinc-400">{action.summary}</p>
                        )}
                        {action.raw && !action.summary && (
                          <p className="text-xs text-zinc-500 font-mono">{action.raw}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Conversation Snapshot */}
              {selectedFeedback.conversation_snapshot && selectedFeedback.conversation_snapshot.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Conversation Snapshot
                  </div>
                  <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                    {selectedFeedback.conversation_snapshot.map((msg) => (
                      <div key={msg.id} className={`rounded-lg px-3 py-2 text-sm border ${msg.role === "assistant" ? "bg-indigo-500/5 border-indigo-500/10 text-zinc-300" : "bg-zinc-900 border-zinc-800 text-zinc-300"}`}>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className={`text-[10px] font-bold uppercase tracking-wide ${msg.role === "assistant" ? "text-indigo-400" : "text-zinc-500"}`}>
                            {msg.role}
                          </span>
                          {msg.agent_id && (
                            <span className="text-[10px] text-zinc-600">• {msg.agent_id}</span>
                          )}
                        </div>
                        <p className="text-sm text-zinc-300 whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tool Calls */}
              {selectedFeedback.tool_calls_log && selectedFeedback.tool_calls_log.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <Wrench className="h-3.5 w-3.5" />
                    Tool Calls
                  </div>
                  <div className="space-y-2">
                    {selectedFeedback.tool_calls_log.map((tc, i) => {
                      const expanded = expandedToolCalls.has(i);
                      const resultStr = tc.result !== undefined ? JSON.stringify(tc.result) : "";
                      return (
                        <div key={i} className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2">
                          <div className="flex items-center justify-between mb-1">
                            <div className="text-xs font-semibold text-indigo-300">{tc.tool || "unknown tool"}</div>
                            {resultStr.length > 200 && (
                              <button
                                onClick={() => toggleToolCall(i)}
                                className="flex items-center gap-0.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition"
                              >
                                {expanded ? (
                                  <><ChevronUp className="h-3 w-3" /> Less</>
                                ) : (
                                  <><ChevronDown className="h-3 w-3" /> More</>
                                )}
                              </button>
                            )}
                          </div>
                          <div className="text-[11px] text-zinc-500 font-mono bg-zinc-950 rounded px-2 py-1 overflow-x-auto">
                            {tc.tool === "retrieve" && tc.args?.sources === null ? (
                              <div>
                                <span className="text-[10px] text-amber-500/80 bg-amber-500/10 rounded px-1.5 py-0.5">sources: agent defaults</span>
                                <pre className="mt-1">{JSON.stringify({ ...tc.args, sources: undefined }, null, 2)}</pre>
                              </div>
                            ) : (
                              JSON.stringify(tc.args || {}, null, 2)
                            )}
                          </div>
                          {tc.result !== undefined && (
                            <div className="mt-1.5 text-[11px] text-zinc-400 font-mono bg-zinc-950 rounded px-2 py-1 overflow-x-auto whitespace-pre-wrap">
                              {expanded ? resultStr : resultStr.slice(0, 200) + (resultStr.length > 200 ? "…" : "")}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Retrieved Sources */}
              {selectedFeedback.retrieved_sources && selectedFeedback.retrieved_sources.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <FileText className="h-3.5 w-3.5" />
                    Retrieved Sources ({selectedFeedback.retrieved_sources.length})
                  </div>
                  <div className="space-y-2">
                    {selectedFeedback.retrieved_sources.map((src, i) => {
                      const expanded = expandedSources.has(i);
                      return (
                        <div
                          key={i}
                          className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 cursor-pointer hover:border-zinc-700 transition"
                          onClick={() => toggleSource(i)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 rounded px-1.5 py-0.5 shrink-0">[{src.rank}]</span>
                              <span className="text-[11px] font-medium text-zinc-300 truncate">{src.title || "Untitled"}</span>
                            </div>
                            {expanded ? (
                              <ChevronUp className="h-3 w-3 text-zinc-500 shrink-0" />
                            ) : (
                              <ChevronDown className="h-3 w-3 text-zinc-500 shrink-0" />
                            )}
                          </div>
                          {src.url && (
                            <div className="text-[10px] text-zinc-600 truncate mt-1">{src.url}</div>
                          )}
                          <div className="text-[10px] text-zinc-600 font-mono mt-0.5">ID: {src.id?.slice(0, 8)}…</div>
                          {expanded && (
                            <div className="mt-2 pt-2 border-t border-zinc-800">
                              <a
                                href={src.url || "#"}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[10px] text-indigo-400 hover:text-indigo-300 transition mb-1.5 inline-block"
                                onClick={(e) => e.stopPropagation()}
                              >
                                Open source →
                              </a>
                              <div className="text-[10px] text-zinc-500 font-mono bg-zinc-950 rounded px-2 py-1.5 overflow-x-auto whitespace-pre-wrap">
                                Source: {src.title}
                                <br />
                                ID: {src.id}
                                {src.url && <><br />URL: {src.url}</>}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Screenshot */}
              {selectedFeedback.screenshot_attachment_id && (
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-400 mb-1.5">
                    <Eye className="h-3.5 w-3.5" />
                    Screenshot
                  </div>
                  <div className="text-xs text-zinc-500">
                    Attachment ID: {selectedFeedback.screenshot_attachment_id}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Test draft chat modal */}
      {showTestDraft && selected && (
        <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-2xl flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-lg">Test Draft</h2>
                <p className="text-xs text-zinc-500">
                  Runs the full agent graph with your draft config — including tools, retrieval, routing, and orchestration.
                </p>
              </div>
              <button
                onClick={() => { setShowTestDraft(false); setTestDraftMessage(""); setTestDraftResponse(""); }}
                className="text-zinc-500 hover:text-zinc-300 transition"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2 flex-1 overflow-y-auto">
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Your message</span>
                <textarea
                  value={testDraftMessage}
                  onChange={(e) => setTestDraftMessage(e.target.value)}
                  placeholder="Type a test message..."
                  rows={3}
                  className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition resize-y"
                />
              </label>

              <div className="flex justify-end">
                <button
                  onClick={handleTestDraft}
                  disabled={testingDraft || !testDraftMessage.trim()}
                  className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-3 py-2 rounded-lg text-sm font-medium transition"
                >
                  {testingDraft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />}
                  {testingDraft ? "Testing…" : "Send"}
                </button>
              </div>

              {testDraftResponse && (
                <div className="mt-3">
                  <span className="text-xs font-medium text-zinc-400">Response</span>
                  <div className="mt-1 bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm text-zinc-300 whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {testDraftResponse}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Eval Test Modal */}
      {showEvalTestModal && selected && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => setShowEvalTestModal(false)}>
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h2 className="font-semibold text-lg">{editingEvalTest ? "Edit Test" : "New Eval Test"}</h2>
              <button onClick={() => setShowEvalTestModal(false)} className="text-zinc-500 hover:text-zinc-300 transition"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Name</span>
                <input
                  value={evalTestForm.name}
                  onChange={(e) => setEvalTestForm((p) => ({ ...p, name: e.target.value }))}
                  className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 outline-none transition"
                  placeholder="e.g., Laptop request for new hire"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Question</span>
                <textarea
                  value={evalTestForm.question}
                  onChange={(e) => setEvalTestForm((p) => ({ ...p, question: e.target.value }))}
                  rows={3}
                  className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 outline-none transition resize-y"
                  placeholder="What question should the agent answer?"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Expected Answer</span>
                <textarea
                  value={evalTestForm.expected_answer}
                  onChange={(e) => setEvalTestForm((p) => ({ ...p, expected_answer: e.target.value }))}
                  rows={4}
                  className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 outline-none transition resize-y"
                  placeholder="What should the ideal answer contain?"
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button onClick={() => setShowEvalTestModal(false)} className="px-4 py-2 rounded-lg text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 transition">Cancel</button>
              <button
                onClick={async () => {
                  if (!evalTestForm.name.trim() || !evalTestForm.question.trim() || !evalTestForm.expected_answer.trim()) return;
                                    try {
                    if (editingEvalTest) {
                      await api.updateEvalTest(selected.slug, editingEvalTest.id, evalTestForm);
                    } else {
                      await api.createEvalTest(selected.slug, evalTestForm);
                    }
                    setShowEvalTestModal(false);
                    loadEvalData(selected.slug);
                    // Re-sync selected agent to prevent stale status
                    try {
                      const agents = await api.listAgentSettings();
                      const updated = agents.find((a) => a.slug === selected.slug);
                      if (updated) setSelected(updated);
                    } catch { /* ignore */ }
                  } catch {
                    alert("Failed to save test");
                  }
                }}
                disabled={!evalTestForm.name.trim() || !evalTestForm.question.trim() || !evalTestForm.expected_answer.trim()}
                className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                <Save className="h-4 w-4" /> Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Launch Run Modal */}
      {showLaunchRunModal && selected && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => setShowLaunchRunModal(false)}>
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
              <h2 className="font-semibold text-lg">Launch Evaluation Run</h2>
              <button onClick={() => setShowLaunchRunModal(false)} className="text-zinc-500 hover:text-zinc-300 transition"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs font-medium text-zinc-400">Run Name</span>
                <input
                  value={launchRunForm.name}
                  onChange={(e) => setLaunchRunForm((p) => ({ ...p, name: e.target.value }))}
                  className="w-full bg-zinc-900/60 border border-zinc-800/60 rounded-xl px-3 py-2 text-sm mt-1 text-zinc-200 focus:border-indigo-500/50 outline-none transition"
                />
              </label>
              <div className="space-y-3">
                <span className="text-xs font-medium text-zinc-400 block">Per-Metric Thresholds</span>
                {Object.entries(launchRunForm.thresholds).map(([key, value]) => (
                  <label key={key} className="block">
                    <span className="text-xs text-zinc-400 capitalize">{key.replace(/_/g, " ")}: {value.toFixed(2)}</span>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.05}
                      value={value}
                      onChange={(e) =>
                        setLaunchRunForm((p) => ({
                          ...p,
                          thresholds: { ...p.thresholds, [key]: parseFloat(e.target.value) },
                        }))
                      }
                      className="w-full mt-1 accent-indigo-500"
                    />
                  </label>
                ))}
              </div>
              <div>
                <span className="text-xs font-medium text-zinc-400 block mb-2">Tests to run</span>
                <div className="max-h-48 overflow-y-auto space-y-1.5 border border-zinc-800 rounded-lg p-2 bg-zinc-900/50">
                  {evalTests.map((t) => (
                    <label key={t.id} className="flex items-center gap-2 cursor-pointer hover:bg-zinc-800/50 rounded px-1.5 py-1 transition">
                      <input
                        type="checkbox"
                        checked={launchRunForm.selectedTestIds.has(t.id)}
                        onChange={(e) => {
                          setLaunchRunForm((p) => {
                            const next = new Set(p.selectedTestIds);
                            if (e.target.checked) next.add(t.id);
                            else next.delete(t.id);
                            return { ...p, selectedTestIds: next };
                          });
                        }}
                        className="accent-indigo-500"
                      />
                      <span className="text-xs text-zinc-300">{t.name}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button onClick={() => setShowLaunchRunModal(false)} className="px-4 py-2 rounded-lg text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 transition">Cancel</button>
              <button
                onClick={async () => {
                  if (!launchRunForm.name.trim() || launchRunForm.selectedTestIds.size === 0) return;
                                    try {
                    await api.createEvalRun(selected.slug, {
                      name: launchRunForm.name,
                      test_ids: Array.from(launchRunForm.selectedTestIds),
                      thresholds: launchRunForm.thresholds,
                    });
                    setShowLaunchRunModal(false);
                    setEvalSubTab("runs");
                    loadEvalData(selected.slug);
                    // Re-sync selected agent to prevent stale status
                    try {
                      const agents = await api.listAgentSettings();
                      const updated = agents.find((a) => a.slug === selected.slug);
                      if (updated) setSelected(updated);
                    } catch { /* ignore */ }
                  } catch {
                    alert("Failed to launch run");
                  }
                }}
                disabled={!launchRunForm.name.trim() || launchRunForm.selectedTestIds.size === 0}
                className="flex items-center gap-1.5 bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium transition"
              >
                <Rocket className="h-4 w-4" /> Launch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Run Detail Modal */}
      {selectedEvalRun && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={() => setSelectedEvalRun(null)}>
          <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
              <div>
                <h2 className="font-semibold text-lg">{selectedEvalRun.name}</h2>
                <p className="text-xs text-zinc-500">
                  {selectedEvalRun.status} • Thresholds: {Object.entries(selectedEvalRun.thresholds || {}).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v.toFixed(2)}`).join(", ")} •
                  Pass: {selectedEvalRun.pass_count}/{selectedEvalRun.total_tests}
                </p>
              </div>
              <button onClick={() => setSelectedEvalRun(null)} className="text-zinc-500 hover:text-zinc-300 transition"><X className="h-5 w-5" /></button>
            </div>
            <div className="px-6 py-5 space-y-6">
              {selectedEvalRun.results.length === 0 ? (
                <p className="text-sm text-zinc-500 text-center py-8">No results yet.</p>
              ) : (
                selectedEvalRun.results.map((res) => (
                  <div key={res.id} className="border border-zinc-800 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-zinc-300">{res.test_name}</span>
                      <div className="flex items-center gap-2">
                        {res.passed !== null && (
                          <span className={`text-[10px] font-bold uppercase tracking-wide rounded px-1.5 py-0.5 ${res.passed ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"}`}>
                            {res.passed ? "PASS" : "FAIL"}
                          </span>
                        )}
                        <span className="text-xs text-zinc-500 font-mono">{res.duration_ms}ms</span>
                      </div>
                    </div>
                    {res.metrics && (
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(res.metrics).map(([k, v]) => {
                          const metricPassed = res.metric_passes?.[k] ?? false;
                          return (
                            <span key={k} className={`text-[10px] border rounded px-1.5 py-0.5 ${metricPassed ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-rose-500/10 border-rose-500/20 text-rose-400"}`}>
                              {k.replace(/_/g, " ")}: {typeof v === "number" ? v.toFixed(2) : v}
                            </span>
                          );
                        })}
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl p-2.5">
                        <span className="text-zinc-500 block mb-1">Expected</span>
                        <p className="text-zinc-300 whitespace-pre-wrap max-h-32 overflow-y-auto">{res.test_name ? evalTests.find((t) => t.id === res.test_id)?.expected_answer || "—" : "—"}</p>
                      </div>
                      <div className="bg-zinc-900/60 border border-zinc-800/60 rounded-xl p-2.5">
                        <span className="text-zinc-500 block mb-1">Actual</span>
                        <p className="text-zinc-300 whitespace-pre-wrap max-h-32 overflow-y-auto">{res.actual_answer || "—"}</p>
                      </div>
                    </div>
                    {res.retrieved_contexts && res.retrieved_contexts.length > 0 && (
                      <div>
                        <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Retrieved Contexts ({res.retrieved_contexts.length})</span>
                        <div className="mt-1 space-y-1">
                          {res.retrieved_contexts.map((ctx, i) => (
                            <button
                              key={i}
                              onClick={() => setSelectedContext(ctx)}
                              className="text-left w-full text-[10px] text-zinc-500 font-mono bg-zinc-950 rounded px-2 py-1 truncate cursor-pointer hover:bg-zinc-800 transition"
                              title="Click to view full context"
                            >
                              <span className="text-zinc-600 mr-1">#{i + 1}</span>{ctx.slice(0, 120)}…
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Full Context Modal */}
      {selectedContext && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[60] p-4" onClick={() => setSelectedContext(null)}>
          <div className="bg-zinc-950 border border-zinc-800 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto shadow-2xl p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-zinc-800">
              <h3 className="text-sm font-medium text-zinc-300">Full Retrieved Context</h3>
              <button onClick={() => setSelectedContext(null)} className="text-zinc-500 hover:text-zinc-300 transition"><X className="h-4 w-4" /></button>
            </div>
            <pre className="text-xs text-zinc-400 font-mono whitespace-pre-wrap break-words">{selectedContext}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
