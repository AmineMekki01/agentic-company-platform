import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Store, Bot, ChevronRight, Wrench, Rocket, BookOpen, Eye, X, Check, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api, type AgentTemplate, type AgentTemplateDetail, type AgentTemplateDeployRequest, type Connector, type AgentSetting } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

const TAG_COLORS: Record<string, string> = {
  starter: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  general: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  research: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  support: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  it: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  hr: "bg-pink-500/10 text-pink-400 border-pink-500/20",
  finance: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  coding: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  sales: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
};

function tagColor(tag: string): string {
  return TAG_COLORS[tag] || "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
}

export default function AdminAgentTemplates() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplateDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [deployForm, setDeployForm] = useState<AgentTemplateDeployRequest>({ slug: "" });
  const [deployError, setDeployError] = useState<string | null>(null);
  const [deployedSlug, setDeployedSlug] = useState<string | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [agents, setAgents] = useState<AgentSetting[]>([]);

  const loadTemplates = async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, connData, agentData] = await Promise.all([
        api.listAgentTemplates(),
        api.listConnectors(),
        api.listAgentSettings(),
      ]);
      setTemplates(data);
      setConnectors(connData);
      setAgents(agentData);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const openPreview = async (id: string) => {
    setPreviewLoading(true);
    setSelectedTemplate(null);
    try {
      const detail = await api.getAgentTemplate(id);
      setSelectedTemplate(detail);
      const suggested = `${detail.id}-1`;
      setDeployForm({ slug: suggested, name: detail.name, description: detail.description || "" });
      setDeployError(null);
      setDeployedSlug(null);
    } catch (e: unknown) {
      const err = e as Error;
      setError(err.message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setSelectedTemplate(null);
    setDeployError(null);
    setDeployedSlug(null);
  };

  const handleDeploy = async () => {
    if (!selectedTemplate || !deployForm.slug.trim()) return;
    setDeploying(true);
    setDeployError(null);
    try {
      const result = await api.deployAgentTemplate(selectedTemplate.id, {
        slug: deployForm.slug.trim(),
        name: deployForm.name?.trim() || undefined,
        description: deployForm.description?.trim() || undefined,
      });
      setDeployedSlug(result.slug);
      setTimeout(() => {
        navigate("/admin/agents", { state: { selectedSlug: result.slug } });
      }, 1200);
    } catch (e: unknown) {
      const err = e as Error;
      setDeployError(err.message);
    } finally {
      setDeploying(false);
    }
  };

  const agentConfig = selectedTemplate?.agent_config || {};
  const tools = (agentConfig.tools as string[] | undefined) || [];
  const connectedSources = (agentConfig.connected_sources as string[] | undefined) || [];
  const workflows = selectedTemplate?.workflows || [];
  const isOrchestrator = Boolean(agentConfig.is_orchestrator);
  const isRouter = Boolean(agentConfig.is_router);

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Agent Template Gallery"
        description="Browse pre-configured agents and deploy them with one click"
        icon={Store}
      />

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading templates…
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => openPreview(t.id)}
              className="group relative flex flex-col gap-3 rounded-2xl border border-zinc-800/60 bg-zinc-900/40 p-5 text-left shadow-sm backdrop-blur-sm transition-all duration-200 hover:border-zinc-700/60 hover:bg-zinc-900/60 hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/10 ring-1 ring-white/5 transition group-hover:bg-indigo-500/15">
                    <Bot className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-zinc-200 group-hover:text-white transition">
                      {t.name}
                    </h3>
                    <p className="text-xs text-zinc-500">{t.id}</p>
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-zinc-600 transition-all group-hover:translate-x-0.5 group-hover:text-zinc-400" />
              </div>
              <p className="text-sm text-zinc-400 line-clamp-2">{t.description}</p>
              <div className="mt-auto flex flex-wrap gap-1.5">
                {t.tags.map((tag) => (
                  <span
                    key={tag}
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${tagColor(tag)}`}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Preview / Deploy Modal */}
      {selectedTemplate && (
        <div className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="animate-scale-in w-full max-w-lg rounded-2xl border border-zinc-800/80 bg-zinc-950 p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/10">
                  <Bot className="h-5 w-5 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-zinc-100">{selectedTemplate.name}</h2>
                  <p className="text-xs text-zinc-500">{selectedTemplate.id}</p>
                </div>
              </div>
              <button
                onClick={closePreview}
                className="rounded-lg p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mb-4 text-sm text-zinc-400">{selectedTemplate.description}</p>

            {/* Template details */}
            <div className="mb-5 space-y-3 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-4">
              <div className="flex items-center gap-2 text-sm text-zinc-300">
                <Eye className="h-4 w-4 text-zinc-500" />
                <span className="font-medium">Model:</span>
                <span className="text-zinc-400">{(agentConfig.llm_model as string) || "default"}</span>
              </div>
              {tools.length > 0 && (
                <div className="flex items-start gap-2 text-sm text-zinc-300">
                  <Wrench className="mt-0.5 h-4 w-4 text-zinc-500" />
                  <span className="font-medium">Tools:</span>
                  <span className="text-zinc-400">{tools.join(", ")}</span>
                </div>
              )}
              {connectedSources.length > 0 && (
                <div className="flex items-start gap-2 text-sm text-zinc-300">
                  <BookOpen className="mt-0.5 h-4 w-4 text-zinc-500" />
                  <span className="font-medium">Knowledge:</span>
                  <span className="text-zinc-400">{connectedSources.length} source(s)</span>
                </div>
              )}
              {workflows.length > 0 && (
                <div className="flex items-center gap-2 text-sm text-zinc-300">
                  <Rocket className="h-4 w-4 text-zinc-500" />
                  <span className="font-medium">Workflows:</span>
                  <span className="text-zinc-400">{workflows.length}</span>
                </div>
              )}
              {isRouter && (
                <div className="flex items-center gap-2 text-sm text-amber-300">
                  <Rocket className="h-4 w-4 text-amber-500" />
                  <span className="font-medium">Router enabled</span>
                </div>
              )}
              {isOrchestrator && (
                <div className="flex items-center gap-2 text-sm text-violet-300">
                  <Rocket className="h-4 w-4 text-violet-500" />
                  <span className="font-medium">Orchestrator enabled</span>
                </div>
              )}
            </div>

            {/* Dependencies */}
            <div className="mb-5 space-y-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-500">Dependencies</h3>
              {tools.includes("create_jira_ticket") && (
                <div className="flex items-center gap-2 text-sm">
                  {connectors.some((c) => c.connector_type === "jira") ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      <span className="text-zinc-300">Jira connector configured</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="h-4 w-4 text-amber-400" />
                      <span className="text-amber-300">
                        Jira connector missing — add one in <strong>Connectors</strong> for ticket creation to work
                      </span>
                    </>
                  )}
                </div>
              )}
              {isRouter && (
                <div className="flex items-start gap-2 text-sm text-blue-300">
                  <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-blue-400" />
                  <span>
                    This is a <strong>routing agent</strong>. It classifies user intent and
                    routes conversations to a single specialist agent. You can configure which
                    agents it routes to after deployment in the agent editor.
                  </span>
                </div>
              )}
              {isOrchestrator && (
                <div className="flex items-start gap-2 text-sm text-violet-300">
                  <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-violet-400" />
                  <span>
                    This is an <strong>orchestrator agent</strong>. It coordinates child agents via
                    workflows, gathers their outputs, and synthesizes the final answer. It can invoke
                    multiple agents in a DAG sequence.
                  </span>
                </div>
              )}
              {deployForm.slug.trim() && agents.some((a) => a.slug === deployForm.slug.trim()) && (
                <div className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-rose-400" />
                  <span className="text-rose-300">
                    Slug <code className="rounded bg-zinc-800 px-1 py-0.5 text-xs text-zinc-400">{deployForm.slug.trim()}</code> already exists — choose a different slug
                  </span>
                </div>
              )}
              {!tools.includes("create_jira_ticket") && !isRouter && !isOrchestrator && !agents.some((a) => a.slug === deployForm.slug.trim()) && (
                <p className="text-sm text-zinc-500">No external dependencies required.</p>
              )}
            </div>

            {previewLoading && (
              <div className="mb-4 flex items-center gap-2 text-sm text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading preview…
              </div>
            )}

            {/* Deploy form */}
            {deployedSlug ? (
              <div className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
                <div className="flex items-center gap-2">
                  <Check className="h-4 w-4" />
                  Agent <span className="font-semibold">{deployedSlug}</span> added as draft.
                </div>
                <p className="mt-1 text-xs text-emerald-400/70">Redirecting to agents for review and publish…</p>
              </div>
            ) : (
              <div className="mb-4 space-y-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-400">Slug *</label>
                  <input
                    type="text"
                    value={deployForm.slug}
                    onChange={(e) => setDeployForm((prev) => ({ ...prev, slug: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
                    placeholder="my-agent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-400">Name</label>
                  <input
                    type="text"
                    value={deployForm.name || ""}
                    onChange={(e) => setDeployForm((prev) => ({ ...prev, name: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-400">Description</label>
                  <textarea
                    value={deployForm.description || ""}
                    onChange={(e) => setDeployForm((prev) => ({ ...prev, description: e.target.value }))}
                    rows={2}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
                  />
                </div>
              </div>
            )}

            {deployError && (
              <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
                {deployError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={closePreview}
                className="rounded-lg px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
              >
                Cancel
              </button>
              {!deployedSlug && (
                <button
                  onClick={handleDeploy}
                  disabled={deploying || !deployForm.slug.trim() || agents.some((a) => a.slug === deployForm.slug.trim())}
                  className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deploying ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Adding…
                    </>
                  ) : (
                    <>
                      <Bot className="h-3.5 w-3.5" />
                      Add Agent
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
