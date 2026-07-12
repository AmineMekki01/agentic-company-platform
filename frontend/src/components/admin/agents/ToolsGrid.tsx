import { Wrench } from "lucide-react";
import { AVAILABLE_TOOLS, TOOL_GROUPS, TOOL_INFO } from "./agentUtils";

interface Props {
  selectedTools: string[];
  values: Partial<Record<string, number>>;
  onToggle: (tool: string) => void;
  onValueChange: (key: string, value: number) => void;
}

function ToggleSwitch({ enabled, onClick }: { enabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      onClick={onClick}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 ${
        enabled ? "bg-gradient-to-r from-brand to-violet-600" : "bg-line"
      }`}
    >
      <span
        className={`inline-block h-[18px] w-[18px] transform rounded-full bg-white shadow-sm transition-transform duration-200 ${
          enabled ? "translate-x-[22px]" : "translate-x-1"
        }`}
      />
    </button>
  );
}

export default function ToolsGrid({ selectedTools, values, onToggle, onValueChange }: Props) {
  const groups = TOOL_GROUPS.map((group) => ({
    group,
    tools: AVAILABLE_TOOLS.filter((tool) => (TOOL_INFO[tool]?.group ?? "General") === group),
  })).filter((g) => g.tools.length > 0);

  return (
    <div className="space-y-6">
      {groups.map(({ group, tools }) => (
        <div key={group}>
          <div className="flex items-center gap-2.5 mb-2.5">
            <span className="text-[11px] font-medium uppercase tracking-wide text-tertiary">{group}</span>
            <div className="h-px flex-1 bg-line/60" />
          </div>
          <div className="space-y-2">
            {tools.map((tool) => {
              const info = TOOL_INFO[tool];
              const Icon = info?.icon ?? Wrench;
              const label = info?.label ?? tool.replace(/_/g, " ");
              const enabled = selectedTools.includes(tool);
              const config = info?.config;
              return (
                <div
                  key={tool}
                  className={`flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border px-4 py-3.5 transition-colors duration-150 ${
                    enabled ? "border-brand/25 bg-brand/[0.04]" : "border-line bg-card hover:border-line/80 hover:bg-hover/30"
                  }`}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors duration-150 ${
                        enabled ? "bg-gradient-to-br from-brand to-violet-600 text-white shadow-sm shadow-brand/30" : "bg-hover text-tertiary"
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1 pt-0.5">
                      <span className="text-sm font-medium text-primary">{label}</span>
                      {info?.description && <p className="text-xs text-tertiary mt-0.5 leading-relaxed">{info.description}</p>}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 pl-[52px] sm:pl-0">
                    {enabled && config && (
                      <div className="flex items-center gap-1.5 rounded-lg border border-line bg-canvas pl-2.5 pr-1.5 py-1.5">
                        <span className="text-[11px] text-tertiary whitespace-nowrap">{config.label}</span>
                        <input
                          type="number"
                          min={config.min}
                          max={config.max}
                          value={values[config.key] ?? config.default}
                          onChange={(e) => {
                            const parsed = parseInt(e.target.value, 10);
                            const clamped = Math.min(config.max, Math.max(config.min, Number.isNaN(parsed) ? config.default : parsed));
                            onValueChange(config.key, clamped);
                          }}
                          className="w-9 bg-transparent text-xs font-medium text-primary text-right outline-none [-moz-appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                        />
                      </div>
                    )}
                    <ToggleSwitch enabled={enabled} onClick={() => onToggle(tool)} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
