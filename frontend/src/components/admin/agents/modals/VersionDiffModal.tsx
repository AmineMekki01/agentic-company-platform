import type { AgentSetting, AgentVersionDetail, KnowledgeSource } from "@/lib/api";
import { diffWords, resolveSourceNames, formatDateTime } from "../agentUtils";

interface Props {
  versionDetail: AgentVersionDetail;
  selected: AgentSetting;
  sources: KnowledgeSource[];
  onClose: () => void;
}

export default function VersionDiffModal({ versionDetail, selected, sources, onClose }: Props) {
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

  return (
    <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-canvas border border-line rounded-2xl p-6 w-full max-w-2xl space-y-4 shadow-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">
              Version v{versionDetail.version_number}
            </h2>
            <p className="text-xs text-tertiary">
              {versionDetail.notes || "No notes"} · {formatDateTime(versionDetail.created_at)}
            </p>
          </div>
          <button onClick={onClose} className="text-tertiary hover:text-secondary transition">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3">
          {fields.map(({ key, label, textDiff, sourceNames }) => {
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
              <div key={key} className={`rounded-lg border px-3 py-2 text-sm ${changed ? "border-warning/30 bg-warning-soft/50" : "border-line bg-card/70"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-secondary">{label}</span>
                  {changed && <span className="text-[10px] font-medium text-warning uppercase tracking-wide">Changed</span>}
                </div>
                {textDiff && changed ? (
                  <div className="text-xs leading-relaxed">
                    {diffWords(oldText, newText).map((seg, idx) => (
                      <span
                        key={idx}
                        className={
                          seg.type === "del"
                            ? "bg-danger/20 text-danger line-through decoration-danger px-0.5 rounded"
                            : seg.type === "ins"
                            ? "bg-success/20 text-success px-0.5 rounded"
                            : "text-secondary"
                        }
                      >
                        {seg.text}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-tertiary block mb-0.5">Version</span>
                      <span className="text-secondary font-mono break-all">{oldText}</span>
                    </div>
                    <div>
                      <span className="text-tertiary block mb-0.5">Current Live</span>
                      <span className="text-secondary font-mono break-all">{newText}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-line">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm bg-card hover:bg-hover border border-line/60 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
