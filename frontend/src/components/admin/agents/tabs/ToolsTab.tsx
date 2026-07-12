import type { AgentSetting, AgentSettingCreate } from "@/lib/api";
import ToolsGrid from "../ToolsGrid";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  toggleTool: (agent: AgentSetting | AgentSettingCreate, tool: string) => void;
}

export default function ToolsTab({ selected, setSelected, toggleTool }: Props) {
  return (
    <div className="space-y-4">
      <div>
        <span className="text-xs font-medium text-secondary">Enabled Tools</span>
        <p className="text-xs text-tertiary mt-0.5">Choose what this agent can do beyond answering from its knowledge sources.</p>
      </div>
      <ToolsGrid
        selectedTools={selected.tools || []}
        values={{ web_search_max_results: selected.web_search_max_results, jira_tickets_limit: selected.jira_tickets_limit }}
        onToggle={(tool) => toggleTool(selected, tool)}
        onValueChange={(key, value) => setSelected({ ...selected, [key]: value })}
      />
    </div>
  );
}
