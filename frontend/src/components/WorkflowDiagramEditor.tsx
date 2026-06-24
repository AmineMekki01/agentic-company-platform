import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  Background,
  Controls,
  Edge,
  EdgeChange,
  Handle,
  MarkerType,
  MiniMap,
  Node,
  NodeChange,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  type XYPosition,
  type Connection,
} from "@xyflow/react";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Maximize2,
  Minimize2,
  Plus,
  Trash2,
  WandSparkles,
} from "lucide-react";
import {
  type AgentSetting,
  type AgentWorkflow,
  type AgentWorkflowCreate,
  type WorkflowDefinition,
  type WorkflowEdge,
  type WorkflowInput,
  type WorkflowNode,
  type WorkflowOutput,
  type WorkflowPosition,
} from "@/lib/api";
import "@xyflow/react/dist/style.css";

export type WorkflowDraft = AgentWorkflow | AgentWorkflowCreate;

interface Props {
  workflowKey: string;
  agentSlug: string;
  agents: AgentSetting[];
  workflow: WorkflowDraft | null;
  onChange: (next: WorkflowDraft) => void;
}

type CanvasNodeData = {
  label: string;
  agentSlug: string;
  agentName: string;
  instructions: string;
  inputs: WorkflowInput[];
  outputs: WorkflowOutput[];
  outputVar: string;
} & Record<string, unknown>;

const createDefaultPosition = (index: number): WorkflowPosition => ({
  x: 100 + index * 340,
  y: 120 + (index % 2) * 170,
});

const makeDefaultNode = (
  index: number,
  agents: AgentSetting[],
  ownerSlug: string,
  prevOutputVar?: string,
): WorkflowNode => {
  const agentSlug = agents.find((agent) => agent.slug !== ownerSlug)?.slug ?? "";
  const outputVar = index === 0 ? "result" : `result_${index + 1}`;
  return {
    id: `step_${index + 1}`,
    agent_slug: agentSlug,
    label: `Step ${index + 1}`,
    instructions:
      index === 0
        ? "Inspect the user request and explain the task clearly before returning the result."
        : "Use the upstream step output to continue the workflow and produce the next result.",
    inputs:
      index === 0
        ? [
            {
              name: "query",
              source: "input.query",
              description: "The user's request or message.",
            },
          ]
        : [
            {
              name: "context",
              source: `step_${index}.${prevOutputVar ?? "result"}`,
              description: "Output from the previous step.",
            },
          ],
    outputs: [
      {
        name: outputVar,
        description: "Primary output from this agent.",
      },
    ],
    prompt_template: null,
    output_var: outputVar,
    position: createDefaultPosition(index),
  };
};

const normalizePosition = (position: WorkflowPosition | null | undefined, index: number): XYPosition => ({
  x: position?.x ?? createDefaultPosition(index).x,
  y: position?.y ?? createDefaultPosition(index).y,
});

const serializeNode = (node: Node<CanvasNodeData>): WorkflowNode => ({
  id: node.id,
  agent_slug: node.data.agentSlug,
  label: node.data.label,
  instructions: node.data.instructions,
  inputs: node.data.inputs,
  outputs: node.data.outputs,
  prompt_template: null,
  output_var: node.data.outputVar || "output",
  position: node.position,
});

const serializeEdge = (edge: Edge): WorkflowEdge => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
});

function WorkflowCanvasNode(props: any) {
  const { data, selected } = props as { data: CanvasNodeData; selected?: boolean };
  return (
    <div
      className={
        "relative w-[300px] rounded-2xl border bg-canvas/95 shadow-xl shadow-black/20 backdrop-blur px-4 py-3 transition " +
        (selected
          ? "border-brand/60 ring-2 ring-brand/20"
          : "border-line hover:border-line")
      }
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-3 !w-3 !border-2 !border-line !bg-brand"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-3 !w-3 !border-2 !border-line !bg-brand"
      />

      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand/20 bg-brand/10">
          <Bot className="h-5 w-5 text-brand" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-primary">{data.label}</div>
              <div className="truncate text-[11px] uppercase tracking-wide text-tertiary">
                @{data.agentSlug || "select-agent"}
              </div>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0 text-tertiary" />
          </div>
        </div>
      </div>

      <div className="mt-3 space-y-3 text-xs">
        <div>
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-tertiary">
            What it should do
          </div>
          <div className="line-clamp-3 rounded-lg border border-line bg-card/70 px-2.5 py-2 text-secondary">
            {data.instructions || "Describe what this agent should do in the side panel."}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-tertiary">
              Inputs
            </div>
            <div className="space-y-1">
              {data.inputs.length === 0 && (
                <div className="rounded-md border border-dashed border-line px-2 py-1 text-tertiary">
                  No inputs
                </div>
              )}
              {data.inputs.slice(0, 3).map((input) => (
                <div key={input.name} className="rounded-md border border-line bg-card px-2 py-1 text-secondary">
                  <span className="font-mono text-[11px] text-brand">{input.name}</span>
                  {input.source ? (
                    <span className="ml-1 text-[10px] text-tertiary">← {input.source}</span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-tertiary">
              Outputs
            </div>
            <div className="space-y-1">
              {data.outputs.length === 0 && (
                <div className="rounded-md border border-dashed border-line px-2 py-1 text-tertiary">
                  No outputs
                </div>
              )}
              {data.outputs.slice(0, 3).map((output) => (
                <div key={output.name} className="rounded-md border border-line bg-card px-2 py-1 text-secondary">
                  <span className="font-mono text-[11px] text-success">{output.name}</span>
                  {output.description ? (
                    <span className="ml-1 text-[10px] text-tertiary">— {output.description}</span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        </div>

        {data.outputVar ? (
          <div className="rounded-md border border-brand/20 bg-brand/10 px-2 py-1 text-[11px] text-brand">
            Primary output: <span className="font-mono">{data.outputVar}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function WorkflowDiagramEditor({ workflowKey, agentSlug, agents, workflow, onChange }: Props) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [canvasNodes, setCanvasNodes] = useState<Node<CanvasNodeData>[]>([]);
  const [canvasEdges, setCanvasEdges] = useState<Edge[]>([]);
  const [fullscreen, setFullscreen] = useState(false);
  const workflowRef = useRef(workflow);

  useEffect(() => {
    workflowRef.current = workflow;
  }, [workflow]);

  const availableAgents = useMemo(() => agents, [agents]);

  const activeNode = useMemo(
    () => canvasNodes.find((node) => node.id === selectedNodeId) ?? null,
    [canvasNodes, selectedNodeId]
  );

  const availableVariables = useMemo(() => {
    const refs: Array<{ label: string; value: string }> = [
      { label: "User input", value: "input.query" },
    ];
    if (!workflow) return refs;
    workflow.definition.nodes.forEach((node) => {
      refs.push({
        label: node.label || node.id,
        value: `${node.id}.${node.output_var || "output"}`,
      });
    });
    return refs;
  }, [workflow]);

  const syncToDraft = useCallback(
    (nextNodes: Node<CanvasNodeData>[], nextEdges: Edge[]) => {
      const currentWorkflow = workflowRef.current;
      if (!currentWorkflow) return;
      const definition: WorkflowDefinition = {
        ...currentWorkflow.definition,
        nodes: nextNodes.map(serializeNode),
        edges: nextEdges.map(serializeEdge),
      };
      onChange({ ...currentWorkflow, definition });
    },
    [onChange]
  );

  useEffect(() => {
    const currentWorkflow = workflowRef.current;
    if (!currentWorkflow) {
      setCanvasNodes([]);
      setCanvasEdges([]);
      setSelectedNodeId(null);
      return;
    }

    const nodes = currentWorkflow.definition.nodes.map((node, index) => {
      const outputVar = node.output_var || node.outputs?.[0]?.name || "output";
      const label = node.label || availableAgents.find((a) => a.slug === node.agent_slug)?.name || node.agent_slug || node.id;
      return {
        id: node.id,
        type: "workflowAgent",
        position: normalizePosition(node.position, index),
        data: {
          label,
          agentSlug: node.agent_slug,
          agentName: availableAgents.find((a) => a.slug === node.agent_slug)?.name || node.agent_slug || "Choose agent",
          instructions: node.instructions || "",
          inputs: node.inputs || [],
          outputs: node.outputs || [],
          outputVar,
        },
      } satisfies Node<CanvasNodeData>;
    });

    const edges: Edge[] = currentWorkflow.definition.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: "smoothstep",
      animated: true,
      markerEnd: { type: MarkerType.ArrowClosed },
    }));

    setCanvasNodes(nodes);
    setCanvasEdges(edges);
    setSelectedNodeId(nodes[0]?.id ?? null);
  }, [workflowKey, availableAgents]);

  useEffect(() => {
    syncToDraft(canvasNodes, canvasEdges);
  }, [canvasEdges, canvasNodes, syncToDraft]);

  const updateNode = useCallback(
    (nodeId: string, updater: (node: CanvasNodeData) => CanvasNodeData) => {
      setCanvasNodes((current) =>
        current.map((node) =>
          node.id === nodeId ? { ...node, data: updater(node.data as CanvasNodeData) } : node
        )
      );
    },
    []
  );

  const addStep = () => {
    const nextIndex = canvasNodes.length;
    const previousNode = workflow?.definition?.nodes[nextIndex - 1];
    const previousOutputVar = previousNode?.output_var || previousNode?.outputs?.[0]?.name || "result";
    const newNode = makeDefaultNode(nextIndex, agents, agentSlug, previousOutputVar);

    const nextNodes = [
      ...canvasNodes,
      {
        id: newNode.id,
        type: "workflowAgent",
        position: normalizePosition(newNode.position, nextIndex),
        data: {
          label: newNode.label || newNode.id,
          agentSlug: newNode.agent_slug,
          agentName: availableAgents.find((a) => a.slug === newNode.agent_slug)?.name || newNode.agent_slug || "Choose agent",
          instructions: newNode.instructions || "",
          inputs: newNode.inputs || [],
          outputs: newNode.outputs || [],
          outputVar: newNode.output_var || "output",
        },
      } satisfies Node<CanvasNodeData>,
    ];

    const nextEdges = [...canvasEdges];
    if (canvasNodes.length > 0) {
      const prev = canvasNodes[canvasNodes.length - 1];
      nextEdges.push({
        id: `e_${prev.id}_${newNode.id}`,
        source: prev.id,
        target: newNode.id,
        type: "smoothstep",
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
      });
    }

    setCanvasNodes(nextNodes);
    setCanvasEdges(nextEdges);
    setSelectedNodeId(newNode.id);
  };

  const addBranch = () => {
    if (!activeNode) return;
    const branchIndex = canvasNodes.length;
    const sourceOutputVar = activeNode.data.outputVar || activeNode.data.outputs?.[0]?.name || "result";
    const newNode = makeDefaultNode(branchIndex, agents, agentSlug, sourceOutputVar);

    // Position the branch node below the selected node with some offset
    const sourcePos = activeNode.position;
    const branchPosition: XYPosition = {
      x: sourcePos.x,
      y: sourcePos.y + 240,
    };

    const nextNodes = [
      ...canvasNodes,
      {
        id: newNode.id,
        type: "workflowAgent",
        position: branchPosition,
        data: {
          label: newNode.label || newNode.id,
          agentSlug: newNode.agent_slug,
          agentName: availableAgents.find((a) => a.slug === newNode.agent_slug)?.name || newNode.agent_slug || "Choose agent",
          instructions: newNode.instructions || "",
          inputs: [
            {
              name: "context",
              source: `${activeNode.id}.${sourceOutputVar}`,
              description: `Output from ${activeNode.data.label || activeNode.id}`,
            },
          ],
          outputs: newNode.outputs || [],
          outputVar: newNode.output_var || "output",
        },
      } satisfies Node<CanvasNodeData>,
    ];

    const nextEdges = [
      ...canvasEdges,
      {
        id: `e_${activeNode.id}_${newNode.id}`,
        source: activeNode.id,
        target: newNode.id,
        type: "smoothstep",
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed },
      },
    ];

    setCanvasNodes(nextNodes);
    setCanvasEdges(nextEdges);
    setSelectedNodeId(newNode.id);
  };

  const removeStep = (nodeId: string) => {
    const nextNodes = canvasNodes.filter((node) => node.id !== nodeId);
    const nextEdges = canvasEdges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId);
    setCanvasNodes(nextNodes);
    setCanvasEdges(nextEdges);
    setSelectedNodeId((current) => (current === nodeId ? nextNodes[0]?.id ?? null : current));
  };

  const addInput = (nodeId: string) => {
    updateNode(nodeId, (node) => ({
      ...node,
      inputs: [
        ...node.inputs,
        {
          name: `input_${node.inputs.length + 1}`,
          source: node.inputs.length === 0 ? "input.query" : availableVariables[0]?.value || "input.query",
          description: "",
        },
      ],
    }));
  };

  const addOutput = (nodeId: string) => {
    updateNode(nodeId, (node) => ({
      ...node,
      outputs: [
        ...node.outputs,
        {
          name: `output_${node.outputs.length + 1}`,
          description: "",
        },
      ],
    }));
  };

  const updateInput = (nodeId: string, index: number, patch: Partial<WorkflowInput>) => {
    updateNode(nodeId, (node) => ({
      ...node,
      inputs: node.inputs.map((input, i) => (i === index ? { ...input, ...patch } : input)),
    }));
  };

  const updateOutput = (nodeId: string, index: number, patch: Partial<WorkflowOutput>) => {
    updateNode(nodeId, (node) => ({
      ...node,
      outputs: node.outputs.map((output, i) => (i === index ? { ...output, ...patch } : output)),
    }));
  };

  const removeInput = (nodeId: string, index: number) => {
    updateNode(nodeId, (node) => ({
      ...node,
      inputs: node.inputs.filter((_, i) => i !== index),
    }));
  };

  const removeOutput = (nodeId: string, index: number) => {
    updateNode(nodeId, (node) => ({
      ...node,
      outputs: node.outputs.filter((_, i) => i !== index),
    }));
  };

  const setNodeAgent = (nodeId: string, agentSlugValue: string) => {
    updateNode(nodeId, (node) => ({
      ...node,
      agentSlug: agentSlugValue,
      agentName: availableAgents.find((a) => a.slug === agentSlugValue)?.name || agentSlugValue || "Choose agent",
    }));

    setCanvasNodes((current) =>
      current.map((node) =>
        node.id === nodeId
          ? {
              ...node,
              data: {
                ...node.data,
                agentSlug: agentSlugValue,
                agentName: availableAgents.find((a) => a.slug === agentSlugValue)?.name || agentSlugValue || "Choose agent",
              },
            }
          : node
      )
    );
  };

  const onNodesChange = useCallback((changes: NodeChange[]) => {
    setCanvasNodes((current) => applyNodeChanges(changes, current as any) as unknown as Node<CanvasNodeData>[]);
  }, []);

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    setCanvasEdges((current) => applyEdgeChanges(changes, current as any) as unknown as Edge[]);
  }, []);

  const onConnect = useCallback((connection: Connection) => {
    setCanvasEdges((current) =>
      addEdge(
        {
          ...connection,
          type: "smoothstep",
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed },
        },
        current
      )
    );
  }, []);

  const nodeTypes = useMemo(() => ({ workflowAgent: WorkflowCanvasNode as any }), []);

  if (!workflow) {
    return (
      <div className="rounded-2xl border border-dashed border-line bg-canvas p-6 text-sm text-tertiary">
        Select or create a workflow to build the diagram.
      </div>
    );
  }

  const toggleFullscreen = () => setFullscreen((prev) => !prev);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && fullscreen) {
        setFullscreen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  const editorContent = (
    <>
      <div className={fullscreen ? "grid h-full grid-cols-[minmax(0,1fr)_400px] gap-4" : "grid h-full grid-cols-[minmax(0,1fr)_360px] gap-4"}>
        <div className={fullscreen ? "relative h-full overflow-hidden rounded-2xl border border-line bg-canvas" : "relative h-full overflow-hidden rounded-2xl border border-line bg-canvas"}>
        <Panel position="top-left" className="pointer-events-none z-10">
          <div className="pointer-events-auto flex items-center gap-2 rounded-xl border border-line bg-canvas/95 px-3 py-2 shadow-lg backdrop-blur">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10 text-brand">
              <WandSparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-secondary">Diagram builder</div>
              <div className="text-[11px] text-tertiary">Drag nodes, connect arrows, and describe what each agent expects.</div>
            </div>
          </div>
        </Panel>

        <Panel position="top-right" className="pointer-events-none z-10">
          <div className="pointer-events-auto flex items-center gap-2 rounded-xl border border-line bg-canvas/95 px-2 py-2 shadow-lg backdrop-blur">
            <button
              onClick={addStep}
              className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white transition hover:bg-brand-hover"
            >
              <Plus className="h-3.5 w-3.5" />
              Add node
            </button>
            <button
              onClick={addBranch}
              disabled={!activeNode}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-card px-3 py-2 text-xs font-medium text-secondary transition hover:bg-hover disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus className="h-3.5 w-3.5" />
              Branch
            </button>
            <button
              onClick={() => {
                if (canvasNodes.length === 0) return;
                const last = canvasNodes[canvasNodes.length - 1];
                setCanvasNodes((current) =>
                  current.map((node, index) => ({
                    ...node,
                    position: createDefaultPosition(index),
                  }))
                );
                setSelectedNodeId(last.id);
              }}
              className="rounded-lg border border-line bg-card px-3 py-2 text-xs font-medium text-secondary transition hover:bg-hover"
            >
              Reflow
            </button>
            <button
              onClick={toggleFullscreen}
              title={fullscreen ? "Exit fullscreen" : "Open in fullscreen"}
              className="rounded-lg border border-line bg-card px-2 py-2 text-xs font-medium text-secondary transition hover:bg-hover"
            >
              {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </Panel>

        <ReactFlow
          nodes={canvasNodes}
          edges={canvasEdges}
          nodeTypes={nodeTypes}
          className="h-full w-full"
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedNodeId(node.id)}
          onPaneClick={() => setSelectedNodeId(null)}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
          defaultEdgeOptions={{
            type: "smoothstep",
            animated: true,
            markerEnd: { type: MarkerType.ArrowClosed },
          }}
        >
          <Background gap={20} size={1} color="#27272a" />
          <Controls
            position="bottom-left"
            className="!bg-card/90 !border-line !shadow-lg"
            style={{}}
          />
          <MiniMap
            nodeColor={(node) => (node.id === selectedNodeId ? "#818cf8" : "#3f3f46")}
            maskColor="rgba(9, 9, 11, 0.6)"
          />
        </ReactFlow>

        <div className="absolute bottom-4 right-4 rounded-xl border border-line bg-canvas/95 px-3 py-2 text-xs text-tertiary shadow-lg backdrop-blur">
          Connect the arrows to define the execution order.
        </div>
        </div>

        <aside className="rounded-2xl border border-line bg-canvas p-4 shadow-xl shadow-black/20 overflow-y-auto min-h-0">
        <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
          <div>
            <div className="text-sm font-semibold text-primary">Selected node</div>
            <div className="text-xs text-tertiary">What this agent expects, does, and produces.</div>
          </div>
          {selectedNodeId ? (
            <div className="flex items-center gap-2">
              <button
                onClick={addBranch}
                className="flex items-center gap-1 rounded-lg border border-line bg-card px-2.5 py-1.5 text-xs text-secondary transition hover:bg-hover"
                title="Add branch from this node"
              >
                <Plus className="h-3.5 w-3.5" />
                Branch
              </button>
              <button
                onClick={() => removeStep(selectedNodeId)}
                className="rounded-lg border border-line p-2 text-secondary transition hover:border-danger/30 hover:bg-danger-soft hover:text-danger"
                title="Delete node"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ) : null}
        </div>

        {!activeNode ? (
          <div className="flex h-full flex-col items-center justify-center py-16 text-center text-tertiary">
            <AlertCircle className="mb-3 h-8 w-8 text-tertiary" />
            <p className="text-sm">Click a node to edit it, or add a new node to start building the diagram.</p>
          </div>
        ) : (
          <div className="mt-4 space-y-4 overflow-y-auto pr-1">
            <label className="block">
              <span className="text-xs font-medium text-secondary">Node label</span>
              <input
                value={activeNode.data.label}
                onChange={(e) => updateNode(activeNode.id, (node) => ({ ...node, label: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50"
              />
            </label>

            <label className="block">
              <span className="text-xs font-medium text-secondary">Agent</span>
              <select
                value={activeNode.data.agentSlug}
                onChange={(e) => setNodeAgent(activeNode.id, e.target.value)}
                className="mt-1 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50"
              >
                <option value="">Select agent…</option>
                {availableAgents.map((agent) => (
                  <option key={agent.slug} value={agent.slug}>
                    {agent.name || agent.slug}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-secondary">What should this agent do?</span>
              <textarea
                value={activeNode.data.instructions}
                onChange={(e) => updateNode(activeNode.id, (node) => ({ ...node, instructions: e.target.value }))}
                rows={4}
                className="mt-1 w-full resize-y rounded-lg border border-line bg-card px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50"
                placeholder="Explain the task, success criteria, and any rules for this agent."
              />
            </label>

            <div className="rounded-xl border border-line bg-card p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-secondary">Inputs</div>
                  <div className="text-[11px] text-tertiary">What the agent should expect.</div>
                </div>
                <button
                  onClick={() => addInput(activeNode.id)}
                  className="flex items-center gap-1 rounded-lg border border-line bg-card px-2.5 py-1.5 text-xs text-secondary transition hover:bg-hover"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {activeNode.data.inputs.length === 0 && (
                  <div className="rounded-lg border border-dashed border-line px-3 py-2 text-xs text-tertiary">
                    Add inputs like <span className="font-mono text-brand">query</span>, <span className="font-mono text-brand">context</span>, or <span className="font-mono text-brand">documents</span>.
                  </div>
                )}
                {activeNode.data.inputs.map((input, index) => (
                  <div key={`${input.name}-${index}`} className="rounded-lg border border-line bg-canvas px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="grid flex-1 grid-cols-2 gap-2">
                        <input
                          value={input.name}
                          onChange={(e) => updateInput(activeNode.id, index, { name: e.target.value })}
                          className="rounded-md border border-line bg-card px-2 py-1 text-xs text-primary outline-none"
                          placeholder="name"
                        />
                        <select
                          value={input.source || ""}
                          onChange={(e) => updateInput(activeNode.id, index, { source: e.target.value })}
                          className="rounded-md border border-line bg-card px-2 py-1 text-xs text-primary outline-none"
                        >
                          <option value="">Choose source…</option>
                          {availableVariables.map((variable) => (
                            <option key={variable.value} value={variable.value}>
                              {variable.label} — {variable.value}
                            </option>
                          ))}
                        </select>
                        <input
                          className="col-span-2 rounded-md border border-line bg-card px-2 py-1 text-xs text-primary outline-none"
                          value={input.description || ""}
                          onChange={(e) => updateInput(activeNode.id, index, { description: e.target.value })}
                          placeholder="Description"
                        />
                      </div>
                      <button
                        onClick={() => removeInput(activeNode.id, index)}
                        className="rounded-md p-1.5 text-tertiary transition hover:bg-danger-soft hover:text-danger"
                        title="Remove input"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-line bg-card p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-secondary">Outputs</div>
                  <div className="text-[11px] text-tertiary">What the agent should return.</div>
                </div>
                <button
                  onClick={() => addOutput(activeNode.id)}
                  className="flex items-center gap-1 rounded-lg border border-line bg-card px-2.5 py-1.5 text-xs text-secondary transition hover:bg-hover"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {activeNode.data.outputs.length === 0 && (
                  <div className="rounded-lg border border-dashed border-line px-3 py-2 text-xs text-tertiary">
                    Add outputs like <span className="font-mono text-success">result</span>, <span className="font-mono text-success">summary</span>, or <span className="font-mono text-success">citations</span>.
                  </div>
                )}
                {activeNode.data.outputs.map((output, index) => (
                  <div key={`${output.name}-${index}`} className="rounded-lg border border-line bg-canvas px-3 py-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="grid flex-1 grid-cols-1 gap-2">
                        <input
                          value={output.name}
                          onChange={(e) => updateOutput(activeNode.id, index, { name: e.target.value })}
                          className="rounded-md border border-line bg-card px-2 py-1 text-xs text-primary outline-none"
                          placeholder="name"
                        />
                        <input
                          value={output.description || ""}
                          onChange={(e) => updateOutput(activeNode.id, index, { description: e.target.value })}
                          className="rounded-md border border-line bg-card px-2 py-1 text-xs text-primary outline-none"
                          placeholder="Description"
                        />
                      </div>
                      <button
                        onClick={() => removeOutput(activeNode.id, index)}
                        className="rounded-md p-1.5 text-tertiary transition hover:bg-danger-soft hover:text-danger"
                        title="Remove output"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <label className="block">
              <span className="text-xs font-medium text-secondary">Primary output variable</span>
              <input
                value={activeNode.data.outputVar}
                onChange={(e) => updateNode(activeNode.id, (node) => ({ ...node, outputVar: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-line bg-card px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50"
                placeholder="result"
              />
            </label>

            <div className="rounded-xl border border-brand/20 bg-brand/10 p-3 text-xs text-brand">
              <div className="font-semibold text-brand">Prompting tip</div>
              <p className="mt-1 text-brand/80">
                Describe the task here, define the inputs/outputs, and connect arrows to control which agent feeds the next one.
              </p>
            </div>
          </div>
        )}
        </aside>
      </div>
    </>
  );

  if (fullscreen) {
    return (
      <ReactFlowProvider>
        <div className="fixed inset-0 z-[100] bg-canvas p-4">
          <div className="flex h-full flex-col">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10 text-brand">
                  <WandSparkles className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-primary">Workflow Diagram Builder</div>
                  <div className="text-[11px] text-tertiary">Fullscreen mode — press Esc or click the button to exit</div>
                </div>
              </div>
              <button
                onClick={toggleFullscreen}
                className="flex items-center gap-1.5 rounded-lg border border-line bg-card px-3 py-2 text-xs font-medium text-secondary transition hover:bg-hover"
              >
                <Minimize2 className="h-3.5 w-3.5" />
                Exit fullscreen
              </button>
            </div>
            <div className="flex-1 min-h-0">
              {editorContent}
            </div>
          </div>
        </div>
      </ReactFlowProvider>
    );
  }

  return (
    <ReactFlowProvider>
      {editorContent}
    </ReactFlowProvider>
  );
}
