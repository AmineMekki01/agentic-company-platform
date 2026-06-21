import { useCallback, useEffect, useState } from "react";
import {
  api,
  type AgentSetting,
  type AgentWorkflow,
  type AgentWorkflowCreate,
  type AgentWorkflowUpdate,
  type WorkflowNode,
} from "@/lib/api";
import {
  ArrowLeft,
  Loader2,
  Plus,
  Save,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Bot,
  WandSparkles,
  X,
} from "lucide-react";
import WorkflowDiagramEditor from "@/components/WorkflowDiagramEditor";

interface Props {
  agentSlug: string;
  agents: AgentSetting[];
}

const makeEmptyWorkflow = (): AgentWorkflowCreate => ({
  name: "New Workflow",
  description: "",
  enabled: false,
  definition: {
    input_schema: ["query"],
    nodes: [makeStep(0)],
    edges: [],
    output: "{{step_1.output}}",
  },
});

const makeStep = (index: number, prevOutputVar?: string): WorkflowNode => ({
  id: `step_${index + 1}`,
  agent_slug: "",
  label: `Step ${index + 1}`,
  instructions:
    index === 0
      ? "Inspect the user's request, identify the goal, and return the primary answer for the workflow."
      : "Use the previous step output to continue the workflow and produce the next stage of the answer.",
  inputs:
    index === 0
      ? [
          {
            name: "query",
            source: "input.query",
            description: "The user's original request.",
          },
        ]
      : [
          {
            name: "context",
            source: `step_${index}.${prevOutputVar ?? "result"}`,
            description: "The previous step result.",
          },
        ],
  outputs: [
    {
      name: index === 0 ? "result" : `result_${index + 1}`,
      description: "Primary result produced by this agent.",
    },
  ],
  prompt_template: null,
  output_var: index === 0 ? "result" : `result_${index + 1}`,
  position: { x: 120, y: 120 },
});

export default function AgentWorkflowEditor({ agentSlug, agents }: Props) {
  const [workflows, setWorkflows] = useState<AgentWorkflow[]>([]);
  const [, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [editing, setEditing] = useState<AgentWorkflow | AgentWorkflowCreate | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listAgentWorkflows(agentSlug);
      setWorkflows(data);
      if (selectedWorkflowId) {
        const stillExists = data.find((w) => w.id === selectedWorkflowId);
        if (!stillExists) {
          setSelectedWorkflowId(null);
          setEditing(null);
        }
      }
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, [agentSlug]);

  const startCreate = () => {
    setShowCreate(true);
    setEditing(makeEmptyWorkflow());
    setSelectedWorkflowId(null);
  };

  const startEdit = (wf: AgentWorkflow) => {
    setShowCreate(false);
    setSelectedWorkflowId(wf.id);
    setEditing({ ...wf, definition: { ...wf.definition, nodes: [...wf.definition.nodes], edges: [...wf.definition.edges] } });
  };

  const handleWorkflowChange = useCallback((next: AgentWorkflow | AgentWorkflowCreate) => {
    setEditing(next);
  }, []);

  const closeEditor = () => {
    setShowCreate(false);
    setEditing(null);
    setSelectedWorkflowId(null);
    setError(null);
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      if (showCreate) {
        const created = await api.createAgentWorkflow(agentSlug, editing as AgentWorkflowCreate);
        setShowCreate(false);
        setSelectedWorkflowId(created.id);
        setEditing(created);
      } else if (selectedWorkflowId && "id" in editing) {
        const updated = await api.updateAgentWorkflow(agentSlug, selectedWorkflowId, editing as AgentWorkflowUpdate);
        setEditing(updated);
      }
      await refresh();
      closeEditor();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    setError(null);
    try {
      await api.deleteAgentWorkflow(agentSlug, id);
      if (selectedWorkflowId === id) {
        closeEditor();
      }
      await refresh();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const toggleEnabled = async (wf: AgentWorkflow) => {
    setError(null);
    try {
      await api.updateAgentWorkflow(agentSlug, wf.id, { enabled: !wf.enabled });
      await refresh();
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  const updateMeta = (field: "name" | "description", value: string) => {
    setEditing((prev) => (prev ? { ...prev, [field]: value } : prev));
  };

  const toggleWorkflowEnabled = () => {
    setEditing((prev) => {
      if (!prev) return prev;
      if ("enabled" in prev) {
        return { ...prev, enabled: !prev.enabled };
      }
      return prev;
    });
  };

  const isEditing = editing !== null;

  return (
    <>
      {/* Workflow list — stays in the agent page */}
      <div className="space-y-4">
        {error && !isEditing && (
          <div className="bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
            {error}
          </div>
        )}

        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-zinc-200">Workflows</h3>
          <button
            onClick={startCreate}
            className="flex items-center gap-1.5 text-xs bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-2.5 py-1.5 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
          >
            <Plus className="h-3 w-3" />
            New Workflow
          </button>
        </div>

        {workflows.length === 0 && !showCreate && (
          <div className="rounded-2xl border border-zinc-800/60 bg-zinc-900/40 p-6 text-center shadow-sm backdrop-blur-sm">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-zinc-800/60 ring-1 ring-white/5">
              <Bot className="h-6 w-6 text-zinc-600" />
            </div>
            <p className="text-sm text-zinc-500">No workflows yet. Create one to define an agent-to-agent pipeline.</p>
          </div>
        )}

        <div className="space-y-2">
          {workflows.map((wf) => (
            <div
              key={wf.id}
              onClick={() => startEdit(wf)}
              className="group flex items-center justify-between rounded-xl border border-zinc-800/60 bg-zinc-900/40 px-3 py-3 cursor-pointer transition-all duration-200 hover:border-zinc-700/60 hover:bg-zinc-900/60"
            >
              <div className="flex items-center gap-3 min-w-0">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleEnabled(wf);
                  }}
                  className="shrink-0"
                  title={wf.enabled ? "Enabled" : "Disabled"}
                >
                  {wf.enabled ? (
                    <ToggleRight className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <ToggleLeft className="h-5 w-5 text-zinc-600" />
                  )}
                </button>
                <div className="min-w-0">
                  <div className="text-sm font-medium text-zinc-200 truncate">{wf.name}</div>
                  <div className="text-xs text-zinc-500 truncate">{wf.description || "No description"}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-600 group-hover:text-zinc-500 transition">
                  {wf.enabled ? "Active" : "Inactive"}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    remove(wf.id);
                  }}
                  className="rounded-lg p-1.5 text-zinc-600 hover:text-red-400 hover:bg-red-500/10 transition"
                  title="Delete workflow"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Full-screen workflow configuration overlay */}
      {isEditing && (
        <div className="fixed inset-0 z-[90] flex flex-col bg-zinc-950 animate-fade-in">
          {/* Header bar */}
          <div className="flex items-center gap-4 border-b border-zinc-800/60 px-6 py-4 bg-zinc-950/80 backdrop-blur-sm">
            <button
              onClick={closeEditor}
              className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900/60 hover:text-zinc-200 transition"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="hidden sm:inline">Back to Agent</span>
            </button>

            <div className="h-6 w-px bg-zinc-800/60" />

            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 ring-1 ring-white/5">
              <WandSparkles className="h-4 w-4 text-indigo-400" />
            </div>

            <div className="flex flex-1 items-center gap-3 min-w-0">
              <input
                value={editing.name}
                onChange={(e) => updateMeta("name", e.target.value)}
                placeholder="Workflow name"
                className="min-w-0 flex-1 rounded-xl border border-zinc-800/60 bg-zinc-900/60 px-3 py-2 text-sm font-medium text-zinc-100 outline-none transition focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10"
              />
              <button
                onClick={toggleWorkflowEnabled}
                className="flex items-center gap-2 rounded-xl border border-zinc-800/60 bg-zinc-900/60 px-3 py-2 text-sm transition hover:bg-zinc-800/60"
                title="Toggle enabled"
              >
                {"enabled" in editing && editing.enabled ? (
                  <ToggleRight className="h-5 w-5 text-emerald-400" />
                ) : (
                  <ToggleLeft className="h-5 w-5 text-zinc-600" />
                )}
                <span className="text-xs font-medium text-zinc-400">
                  {"enabled" in editing && editing.enabled ? "Enabled" : "Disabled"}
                </span>
              </button>
            </div>

            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-1.5 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-4 py-2 text-sm font-medium text-white transition disabled:opacity-50 shadow-lg shadow-indigo-500/15"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Saving…" : "Save & Close"}
            </button>

            <button
              onClick={closeEditor}
              className="rounded-xl p-2 text-zinc-600 hover:bg-zinc-900/60 hover:text-zinc-300 transition"
              aria-label="Close"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Description bar */}
          <div className="flex items-center gap-3 border-b border-zinc-800/40 px-6 py-3 bg-zinc-950/40">
            <span className="text-xs font-medium text-zinc-500 shrink-0">Description</span>
            <input
              value={editing.description || ""}
              onChange={(e) => updateMeta("description", e.target.value)}
              placeholder="What does this workflow do?"
              className="flex-1 rounded-xl border border-zinc-800/40 bg-zinc-900/40 px-3 py-1.5 text-sm text-zinc-300 outline-none transition focus:border-indigo-500/40 focus:ring-2 focus:ring-indigo-500/10"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="mx-6 mt-3 bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
              {error}
            </div>
          )}

          {/* Diagram editor — fills remaining space */}
          <div className="flex-1 min-h-0 p-4">
            <WorkflowDiagramEditor
              workflowKey={selectedWorkflowId ?? (showCreate ? "new-workflow" : "workflow")}
              agentSlug={agentSlug}
              agents={agents}
              workflow={editing}
              onChange={handleWorkflowChange}
            />
          </div>
        </div>
      )}
    </>
  );
}
