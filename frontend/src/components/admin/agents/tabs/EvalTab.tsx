import { Loader2, Plus, Rocket, Settings, Trash2 } from "lucide-react";
import type { AgentEvalTest, AgentEvalRun } from "@/lib/api";

interface Props {
  evalTests: AgentEvalTest[];
  evalRuns: AgentEvalRun[];
  evalLoading: boolean;
  evalSubTab: "tests" | "runs";
  setEvalSubTab: (t: "tests" | "runs") => void;
  onEditTest: (test: AgentEvalTest | null) => void;
  onDeleteTest: (test: AgentEvalTest) => void;
  onLaunchRun: () => void;
  onViewRun: (run: AgentEvalRun) => void;
  onDeleteRun: (run: AgentEvalRun) => void;
}

export default function EvalTab({
  evalTests, evalRuns, evalLoading, evalSubTab, setEvalSubTab,
  onEditTest, onDeleteTest, onLaunchRun, onViewRun, onDeleteRun,
}: Props) {
  return (
    <div className="w-full space-y-6">
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <button
          onClick={() => setEvalSubTab("tests")}
          className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "tests" ? "bg-hover text-primary" : "text-tertiary hover:text-secondary"}`}
        >
          Tests
        </button>
        <button
          onClick={() => setEvalSubTab("runs")}
          className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "runs" ? "bg-hover text-primary" : "text-tertiary hover:text-secondary"}`}
        >
          Runs
        </button>
      </div>

      {evalLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
        </div>
      ) : evalSubTab === "tests" ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-secondary">Evaluation Tests ({evalTests.length})</h3>
            <button
              onClick={() => onEditTest(null)}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
            >
              <Plus className="h-3.5 w-3.5" /> New Test
            </button>
          </div>
          {evalTests.length === 0 ? (
            <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
              <p className="text-sm text-tertiary">No evaluation tests yet.</p>
              <p className="text-xs text-tertiary mt-1">Create tests with a question and expected answer to evaluate your agent.</p>
            </div>
          ) : (
            <div className="rounded-lg border border-line overflow-hidden">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
                  <tr>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Question</th>
                    <th className="px-4 py-2 font-medium">Expected Answer</th>
                    <th className="px-4 py-2 font-medium w-24"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {evalTests.map((t) => (
                    <tr key={t.id} className="hover:bg-hover/70 transition">
                      <td className="px-4 py-2.5 text-secondary font-medium">{t.name}</td>
                      <td className="px-4 py-2.5 text-secondary max-w-xs truncate">{t.question}</td>
                      <td className="px-4 py-2.5 text-secondary max-w-xs truncate">{t.expected_answer}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => onEditTest(t)}
                            className="text-tertiary hover:text-secondary transition"
                            title="Edit"
                          >
                            <Settings className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => onDeleteTest(t)}
                            className="text-tertiary hover:text-danger transition"
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-secondary">Evaluation Runs ({evalRuns.length})</h3>
            <button
              onClick={onLaunchRun}
              disabled={evalTests.length === 0}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
            >
              <Rocket className="h-3.5 w-3.5" /> Launch Run
            </button>
          </div>
          {evalRuns.length === 0 ? (
            <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
              <p className="text-sm text-tertiary">No evaluation runs yet.</p>
              <p className="text-xs text-tertiary mt-1">Launch a run to evaluate your agent against the test cases.</p>
            </div>
          ) : (
            <div className="rounded-lg border border-line overflow-hidden">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
                  <tr>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Pass Rate</th>
                    <th className="px-4 py-2 font-medium">Date</th>
                    <th className="px-4 py-2 font-medium w-24"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {evalRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-hover/70 transition cursor-pointer" onClick={() => onViewRun(r)}>
                      <td className="px-4 py-2.5 text-secondary font-medium">{r.name}</td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${
                          r.status === "completed" ? "bg-success-soft text-success" :
                          r.status === "running" ? "bg-warning-soft text-warning" :
                          r.status === "failed" ? "bg-danger-soft text-danger" :
                          "bg-hover text-secondary"
                        }`}>
                          {r.status === "running" && <Loader2 className="h-3 w-3 animate-spin" />}
                          {r.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        {r.total_tests > 0 ? (
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 bg-hover rounded-full overflow-hidden">
                              <div
                                className="h-full bg-success rounded-full"
                                style={{ width: `${(r.pass_count / r.total_tests) * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-secondary">{r.pass_count}/{r.total_tests}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-tertiary">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-secondary whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                      <td className="px-4 py-2.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); onDeleteRun(r); }}
                          className="text-tertiary hover:text-danger transition"
                          title="Delete"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
