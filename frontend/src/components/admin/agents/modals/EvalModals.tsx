import { X, Rocket, ExternalLink } from "lucide-react";
import type { AgentEvalTestSetDetail, AgentEvalRunDetail } from "@/lib/api";

interface LaunchRunModalProps {
  launchRunForm: {
    name: string;
    thresholds: Record<string, number>;
    selectedTestSetIds: Set<string>;
  };
  setLaunchRunForm: (fn: (p: any) => any) => void;
  evalTestSets: AgentEvalTestSetDetail[];
  onClose: () => void;
  onLaunch: () => void;
}

export function LaunchRunModal({ launchRunForm, setLaunchRunForm, evalTestSets, onClose, onLaunch }: LaunchRunModalProps) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-canvas border border-line rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between pb-3 border-b border-line">
          <h2 className="font-semibold text-lg">Launch Evaluation Run</h2>
          <button onClick={onClose} className="text-tertiary hover:text-secondary transition"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-secondary">Run Name</span>
            <input
              value={launchRunForm.name}
              onChange={(e) => setLaunchRunForm((p) => ({ ...p, name: e.target.value }))}
              className="w-full bg-card border border-line/60 rounded-xl px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 outline-none transition"
            />
          </label>
          <div className="space-y-3">
            <span className="text-xs font-medium text-secondary block">Per-Metric Thresholds</span>
            {Object.entries(launchRunForm.thresholds).map(([key, value]) => (
              <label key={key} className="block">
                <span className="text-xs text-secondary capitalize">{key.replace(/_/g, " ")}: {value.toFixed(2)}</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={value}
                  onChange={(e) =>
                    setLaunchRunForm((p: any) => ({
                      ...p,
                      thresholds: { ...p.thresholds, [key]: parseFloat(e.target.value) },
                    }))
                  }
                  className="w-full mt-1 accent-brand"
                />
              </label>
            ))}
          </div>
          <div>
            <span className="text-xs font-medium text-secondary block mb-2">Test sets to run</span>
            <div className="max-h-48 overflow-y-auto space-y-1.5 border border-line rounded-lg p-2 bg-card/70">
              {evalTestSets.map((ts) => (
                <label key={ts.id} className="flex items-center gap-2 cursor-pointer hover:bg-hover/70 rounded px-1.5 py-1 transition">
                  <input
                    type="checkbox"
                    checked={launchRunForm.selectedTestSetIds.has(ts.id)}
                    onChange={(e) => {
                      setLaunchRunForm((p: any) => {
                        const next = new Set(p.selectedTestSetIds);
                        if (e.target.checked) next.add(ts.id);
                        else next.delete(ts.id);
                        return { ...p, selectedTestSetIds: next };
                      });
                    }}
                    className="accent-brand"
                  />
                  <span className="text-xs text-secondary">{ts.name} <span className="text-tertiary">({ts.tests.length} tests)</span></span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2 border-t border-line">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm bg-card hover:bg-hover border border-line/60 transition">Cancel</button>
          <button
            onClick={onLaunch}
            disabled={!launchRunForm.name.trim() || launchRunForm.selectedTestSetIds.size === 0}
            className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition"
          >
            <Rocket className="h-4 w-4" /> Launch
          </button>
        </div>
      </div>
    </div>
  );
}

interface RunDetailModalProps {
  run: AgentEvalRunDetail;
  onClose: () => void;
  onContextClick: (ctx: string) => void;
}

export function RunDetailModal({ run, onClose, onContextClick }: RunDetailModalProps) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-canvas border border-line rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div>
            <h2 className="font-semibold text-lg flex items-center gap-2">
              {run.name}
              <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                run.config_source === "draft"
                  ? "bg-warning-soft text-warning"
                  : "bg-success-soft text-success"
              }`}>
                {run.config_source === "draft" ? "Draft" : "Published"}
              </span>
            </h2>
            <p className="text-xs text-tertiary">
              {run.status} • Thresholds: {Object.entries(run.thresholds || {}).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v.toFixed(2)}`).join(", ")} •
              Pass: {run.pass_count}/{run.total_tests}
            </p>
          </div>
          <button onClick={onClose} className="text-tertiary hover:text-secondary transition"><X className="h-5 w-5" /></button>
        </div>
        <div className="px-6 py-5 space-y-6">
          {run.results.length === 0 ? (
            <p className="text-sm text-tertiary text-center py-8">No results yet.</p>
          ) : (
            run.results.map((res) => (
              <div key={res.id} className="border border-line rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-secondary">{res.test_name || res.test_id}</span>
                  <div className="flex items-center gap-2">
                    {res.passed !== null && (
                      <span className={`text-[10px] font-bold uppercase tracking-wide rounded px-1.5 py-0.5 ${res.passed ? "bg-success-soft text-success" : "bg-danger-soft text-danger"}`}>
                        {res.passed ? "PASS" : "FAIL"}
                      </span>
                    )}
                    <span className="text-xs text-tertiary font-mono">{res.duration_ms}ms</span>
                    {res.trace_url && (
                      <a
                        href={res.trace_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-[10px] text-brand hover:underline"
                        title="View full trace in Langfuse"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Trace
                      </a>
                    )}
                  </div>
                </div>
                {res.metrics && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(res.metrics).map(([k, v]) => {
                      const metricPassed = res.metric_passes?.[k] ?? false;
                      return (
                        <span key={k} className={`text-[10px] border rounded px-1.5 py-0.5 ${metricPassed ? "bg-success-soft border-success/20 text-success" : "bg-danger-soft border-danger/20 text-danger"}`}>
                          {k.replace(/_/g, " ")}: {typeof v === "number" ? v.toFixed(2) : v}
                        </span>
                      );
                    })}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-card border border-line/60 rounded-xl p-2.5">
                    <span className="text-tertiary block mb-1">Actual</span>
                    <p className="text-secondary whitespace-pre-wrap max-h-32 overflow-y-auto">{res.actual_answer || "—"}</p>
                  </div>
                  <div className="bg-card border border-line/60 rounded-xl p-2.5">
                    <span className="text-tertiary block mb-1">Score</span>
                    <p className="text-secondary whitespace-pre-wrap max-h-32 overflow-y-auto">{res.score !== null ? res.score.toFixed(3) : "—"}</p>
                  </div>
                </div>
                {res.retrieved_contexts && res.retrieved_contexts.length > 0 && (
                  <div>
                    <span className="text-[10px] text-tertiary uppercase tracking-wide">Retrieved Contexts ({res.retrieved_contexts.length})</span>
                    <div className="mt-1 space-y-1">
                      {res.retrieved_contexts.map((ctx, i) => (
                        <button
                          key={i}
                          onClick={() => onContextClick(ctx)}
                          className="text-left w-full text-[10px] text-tertiary font-mono bg-canvas rounded px-2 py-1 truncate cursor-pointer hover:bg-hover transition"
                          title="Click to view full context"
                        >
                          <span className="text-tertiary mr-1">#{i + 1}</span>{ctx.slice(0, 120)}…
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
  );
}

export function ContextModal({ context, onClose }: { context: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[60] p-4" onClick={onClose}>
      <div className="bg-canvas border border-line rounded-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto shadow-2xl p-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3 pb-2 border-b border-line">
          <h3 className="text-sm font-medium text-secondary">Full Retrieved Context</h3>
          <button onClick={onClose} className="text-tertiary hover:text-secondary transition"><X className="h-4 w-4" /></button>
        </div>
        <pre className="text-xs text-secondary font-mono whitespace-pre-wrap break-words">{context}</pre>
      </div>
    </div>
  );
}
