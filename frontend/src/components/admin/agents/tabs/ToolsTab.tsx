import type { AgentSetting, AgentSettingCreate } from "@/lib/api";
import { AVAILABLE_TOOLS } from "../agentUtils";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  toggleTool: (agent: AgentSetting | AgentSettingCreate, tool: string) => void;
}

export default function ToolsTab({ selected, toggleTool }: Props) {
  return (
    <div className="space-y-4">
      <div className="block">
        <span className="text-xs font-medium text-secondary">Enabled Tools</span>
        <div className="mt-2 flex flex-wrap gap-3">
          {AVAILABLE_TOOLS.map((tool) => (
            <label key={tool} className="flex items-center gap-1.5 text-sm text-secondary cursor-pointer">
              <input
                type="checkbox"
                checked={(selected.tools || []).includes(tool)}
                onChange={() => toggleTool(selected, tool)}
                className="accent-brand"
              />
              <span className="capitalize">{tool.replace(/_/g, " ")}</span>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
