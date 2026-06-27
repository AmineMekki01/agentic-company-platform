import type { AgentSetting, AgentSettingCreate } from "@/lib/api";
import AgentWorkflowEditor from "@/components/AgentWorkflowEditor";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  agents: AgentSetting[];
  toggleRoute: (agent: AgentSetting | AgentSettingCreate, slug: string) => void;
}

export default function AgentToAgentTab({ selected, setSelected, agents, toggleRoute }: Props) {
  return (
    <div className="space-y-6">
      <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-line bg-canvas px-3 py-2.5">
        <input
          type="checkbox"
          checked={selected.is_router || false}
          onChange={(e) => setSelected({ ...selected, is_router: e.target.checked, is_orchestrator: false })}
          className="accent-warning"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Enable Routing</span>
          <span className="block text-xs text-tertiary">
            This agent classifies user intent and routes the conversation to a single specialist agent.
          </span>
        </span>
      </label>

      {selected.is_router && (
        <div className="block">
          <span className="text-xs font-medium text-secondary">Routes To (Specialist Agents)</span>
          <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
            {agents
              .filter((a) => a.slug !== selected.slug)
              .map((a) => {
                const checked = (selected.routes_to || []).includes(a.slug);
                return (
                  <label key={a.slug} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRoute(selected, a.slug)}
                      className="accent-warning"
                    />
                    <span>{a.name || a.slug}</span>
                    <span className="text-xs text-tertiary">@{a.slug}</span>
                  </label>
                );
              })}
            {agents.length <= 1 && (
              <p className="text-xs text-tertiary">No other agents available to route to.</p>
            )}
          </div>
        </div>
      )}

      <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-line bg-canvas px-3 py-2.5">
        <input
          type="checkbox"
          checked={selected.is_orchestrator || false}
          onChange={(e) => setSelected({ ...selected, is_orchestrator: e.target.checked, is_router: false })}
          className="accent-violet-500"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Enable Orchestration</span>
          <span className="block text-xs text-tertiary">
            This agent acts as a supervisor. It can call multiple child agents and synthesize their outputs into a final answer.
          </span>
        </span>
      </label>

      {selected.is_orchestrator && (
        <div className="block">
          <span className="text-xs font-medium text-secondary">Child Agents</span>
          <div className="mt-1 space-y-1 max-h-48 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
            {agents
              .filter((a) => a.slug !== selected.slug)
              .map((a) => {
                const checked = (selected.routes_to || []).includes(a.slug);
                return (
                  <label key={a.slug} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleRoute(selected, a.slug)}
                      className="accent-violet-500"
                    />
                    <span>{a.name || a.slug}</span>
                    <span className="text-xs text-tertiary">@{a.slug}</span>
                  </label>
                );
              })}
            {agents.length <= 1 && (
              <p className="text-xs text-tertiary">No other agents available.</p>
            )}
          </div>
        </div>
      )}

      <div className="border-t border-line pt-4">
        <h3 className="text-sm font-medium text-secondary mb-1">Workflows</h3>
        <p className="text-xs text-tertiary mb-3">
          Define step-by-step DAG pipelines for this agent. Click a workflow or create a new one to open the diagram builder.
        </p>
        <AgentWorkflowEditor agentSlug={selected.slug} agents={agents} />
      </div>
    </div>
  );
}
