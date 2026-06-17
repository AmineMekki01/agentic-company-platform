import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type AgentSetting,
  type AgentWorkflow,
  type AgentWorkflowCreate,
  type AgentWorkflowUpdate,
  type WorkflowNode,
} from "@/lib/api";
import {
  Loader2,
  Plus,
  Save,
  Trash2,
  ChevronRight,
  ToggleLeft,
  ToggleRight,
  Bot,
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
  const editorRef = useRef<HTMLDivElement | null>(null);
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
        } else if (editing && "id" in editing) {
          setEditing(stillExists);
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
    queueMicrotask(() => {
      editorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const startEdit = (wf: AgentWorkflow) => {
    setShowCreate(false);
    setSelectedWorkflowId(wf.id);
    setEditing({ ...wf, definition: { ...wf.definition, nodes: [...wf.definition.nodes], edges: [...wf.definition.edges] } });
    queueMicrotask(() => {
      editorRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const handleWorkflowChange = useCallback((next: AgentWorkflow | AgentWorkflowCreate) => {
    setEditing(next);
  }, []);

  const cancelEdit = () => {
    setShowCreate(false);
    setEditing(null);
    setSelectedWorkflowId(null);
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
        setSelectedWorkflowId(null);
        setEditing(null);
        setShowCreate(false);
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

  const isEditing = editing !== null;

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-950/40 border border-red-800/50 text-red-300 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-red-500 shrink-0" />
          {error}
        </div>
      )}

      {/* Workflow list */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Workflows</h3>
        <button
          onClick={startCreate}
          className="flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 px-2.5 py-1.5 rounded-md font-medium transition"
        >
          <Plus className="h-3 w-3" />
          New Workflow
        </button>
      </div>

      {workflows.length === 0 && !showCreate && (
        <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-6 text-center">
          <Bot className="mx-auto h-8 w-8 text-zinc-700 mb-2" />
          <p className="text-sm text-zinc-500">No workflows yet. Create one to define an agent-to-agent pipeline.</p>
        </div>
      )}

      <div className="space-y-2">
        {workflows.map((wf) => (
          <div
            key={wf.id}
            onClick={() => startEdit(wf)}
            className={
              "flex items-center justify-between rounded-lg border px-3 py-2.5 cursor-pointer transition " +
              (selectedWorkflowId === wf.id
                ? "border-indigo-500/40 bg-indigo-500/5"
                : "border-zinc-800 bg-zinc-950 hover:bg-zinc-900")
            }
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
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  remove(wf.id);
                }}
                className="rounded-md p-1.5 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition"
                title="Delete workflow"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
              <ChevronRight className="h-4 w-4 text-zinc-500" />
            </div>
          </div>
        ))}
      </div>

      {isEditing && (
        <div ref={editorRef} className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-950 p-4">
          <WorkflowDiagramEditor
            workflowKey={selectedWorkflowId ?? (showCreate ? "new-workflow" : "workflow")}
            agentSlug={agentSlug}
            agents={agents}
            workflow={editing}
            onChange={handleWorkflowChange}
          />

          <div className="flex justify-end gap-2 border-t border-zinc-800 pt-4">
            <button
              onClick={cancelEdit}
              className="rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-sm text-zinc-300 transition hover:bg-zinc-900"
            >
              Cancel
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
