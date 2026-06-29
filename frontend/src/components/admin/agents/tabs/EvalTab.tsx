import { useState } from "react";
import { Loader2, Plus, Rocket, Settings, Trash2, Calendar, Clock, Power, ChevronDown, ChevronRight, Pencil } from "lucide-react";
import type { AgentEvalTestSetDetail, AgentEvalRun, AgentEvalSchedule, AgentEvalScheduleCreate, AgentEvalTestCreate } from "@/lib/api";
import { api } from "@/lib/api";

interface Props {
  evalTestSets: AgentEvalTestSetDetail[];
  evalRuns: AgentEvalRun[];
  evalLoading: boolean;
  evalSubTab: "tests" | "runs" | "schedules";
  setEvalSubTab: (t: "tests" | "runs" | "schedules") => void;
  agentSlug: string;
  evalSchedules: AgentEvalSchedule[];
  onSchedulesChanged: () => void;
  onTestDataChanged: () => void;
  onLaunchRun: () => void;
  onViewRun: (run: AgentEvalRun) => void;
  onDeleteRun: (run: AgentEvalRun) => void;
}

const FREQUENCIES = [
  { label: "Minutes", value: "minutes" },
  { label: "Hours", value: "hours" },
  { label: "Days", value: "days" },
  { label: "Weeks", value: "weeks" },
  { label: "Months", value: "months" },
  { label: "Years", value: "years" },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatFrequency(freq: string, interval: number): string {
  const f = FREQUENCIES.find((x) => x.value === freq);
  const label = f ? f.label.toLowerCase() : freq;
  return interval === 1 ? `Every ${label.slice(0, -1)}` : `Every ${interval} ${label}`;
}

function toLocalDatetime(dt: string): string {
  const d = new Date(dt);
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 16);
}

export default function EvalTab({
  evalTestSets, evalRuns, evalLoading, evalSubTab, setEvalSubTab,
  agentSlug, evalSchedules, onSchedulesChanged, onTestDataChanged,
  onLaunchRun, onViewRun, onDeleteRun,
}: Props) {
  const [expandedSets, setExpandedSets] = useState<Set<string>>(new Set());
  const [showTestSetForm, setShowTestSetForm] = useState(false);
  const [editingTestSet, setEditingTestSet] = useState<string | null>(null);
  const [testSetForm, setTestSetForm] = useState({ name: "", description: "" });
  const [showTestForm, setShowTestForm] = useState<string | null>(null);
  const [editingTest, setEditingTest] = useState<{ testSetId: string; testId: string } | null>(null);
  const [testForm, setTestForm] = useState<AgentEvalTestCreate>({ question: "", expected_answer: "" });

  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<AgentEvalSchedule | null>(null);
  const [scheduleForm, setScheduleForm] = useState<AgentEvalScheduleCreate>({
    name: "",
    frequency: "days",
    interval: 1,
    start_date: new Date().toISOString().slice(0, 16),
    end_date: null,
    test_set_ids: [],
    thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
    enabled: true,
  });

  const totalTests = evalTestSets.reduce((sum, ts) => sum + ts.tests.length, 0);

  const toggleSet = (id: string) => {
    setExpandedSets((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleEditTestSet = (id: string | null) => {
    if (id) {
      const ts = evalTestSets.find((t) => t.id === id);
      if (ts) {
        setTestSetForm({ name: ts.name, description: ts.description ?? "" });
        setEditingTestSet(id);
      }
    } else {
      setTestSetForm({ name: "", description: "" });
      setEditingTestSet(null);
    }
    setShowTestSetForm(true);
  };

  const handleSaveTestSet = async () => {
    if (!testSetForm.name.trim()) return;
    try {
      if (editingTestSet) {
        await api.updateEvalTestSet(agentSlug, editingTestSet, testSetForm);
      } else {
        await api.createEvalTestSet(agentSlug, testSetForm);
      }
      setShowTestSetForm(false);
      onTestDataChanged();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save test set");
    }
  };

  const handleDeleteTestSet = async (id: string) => {
    if (!confirm("Delete this test set and all its tests?")) return;
    try {
      await api.deleteEvalTestSet(agentSlug, id);
      onTestDataChanged();
    } catch {
      alert("Failed to delete test set");
    }
  };

  const handleAddTest = (testSetId: string) => {
    setTestForm({ question: "", expected_answer: "" });
    setEditingTest(null);
    setShowTestForm(testSetId);
  };

  const handleEditTest = (testSetId: string, testId: string, question: string, expected_answer: string) => {
    setTestForm({ question, expected_answer });
    setEditingTest({ testSetId, testId });
    setShowTestForm(testSetId);
  };

  const handleSaveTest = async () => {
    if (!testForm.question.trim() || !testForm.expected_answer.trim() || !showTestForm) return;
    try {
      if (editingTest) {
        await api.updateEvalTest(agentSlug, editingTest.testSetId, editingTest.testId, testForm);
      } else {
        await api.createEvalTest(agentSlug, showTestForm, testForm);
      }
      setShowTestForm(null);
      setEditingTest(null);
      onTestDataChanged();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save test");
    }
  };

  const handleDeleteTest = async (testSetId: string, testId: string) => {
    if (!confirm("Delete this test?")) return;
    try {
      await api.deleteEvalTest(agentSlug, testSetId, testId);
      onTestDataChanged();
    } catch {
      alert("Failed to delete test");
    }
  };

  const handleEditSchedule = (s: AgentEvalSchedule | null) => {
    setEditingSchedule(s);
    setScheduleForm(s ? {
      name: s.name,
      frequency: s.frequency,
      interval: s.interval,
      start_date: toLocalDatetime(s.start_date),
      end_date: s.end_date ? toLocalDatetime(s.end_date) : null,
      test_set_ids: s.test_set_ids ?? [],
      thresholds: s.thresholds ?? { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
      enabled: s.enabled,
    } : {
      name: "",
      frequency: "days",
      interval: 1,
      start_date: new Date().toISOString().slice(0, 16),
      end_date: null,
      test_set_ids: [],
      thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
      enabled: true,
    });
    setShowScheduleForm(true);
  };

  const handleSaveSchedule = async () => {
    if (!scheduleForm.name.trim()) return;
    try {
      const payload = {
        ...scheduleForm,
        start_date: new Date(scheduleForm.start_date).toISOString(),
        end_date: scheduleForm.end_date ? new Date(scheduleForm.end_date).toISOString() : null,
      };
      if (editingSchedule) {
        await api.updateEvalSchedule(agentSlug, editingSchedule.id, payload);
      } else {
        await api.createEvalSchedule(agentSlug, payload);
      }
      setShowScheduleForm(false);
      onSchedulesChanged();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save schedule");
    }
  };

  const handleDeleteSchedule = async (s: AgentEvalSchedule) => {
    if (!confirm("Delete this schedule?")) return;
    try {
      await api.deleteEvalSchedule(agentSlug, s.id);
      onSchedulesChanged();
    } catch {
      alert("Failed to delete schedule");
    }
  };

  const handleToggleSchedule = async (s: AgentEvalSchedule) => {
    try {
      await api.updateEvalSchedule(agentSlug, s.id, { enabled: !s.enabled });
      onSchedulesChanged();
    } catch {
      alert("Failed to toggle schedule");
    }
  };

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center gap-2 border-b border-line pb-2">
        <button
          onClick={() => setEvalSubTab("tests")}
          className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "tests" ? "bg-hover text-primary" : "text-tertiary hover:text-secondary"}`}
        >
          Test Sets
        </button>
        <button
          onClick={() => setEvalSubTab("runs")}
          className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "runs" ? "bg-hover text-primary" : "text-tertiary hover:text-secondary"}`}
        >
          Runs
        </button>
        <button
          onClick={() => setEvalSubTab("schedules")}
          className={`text-sm font-medium px-3 py-1.5 rounded-md transition ${evalSubTab === "schedules" ? "bg-hover text-primary" : "text-tertiary hover:text-secondary"}`}
        >
          Schedules
        </button>
      </div>

      {evalLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
        </div>
      ) : evalSubTab === "tests" ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-secondary">Test Sets ({evalTestSets.length}) — {totalTests} tests</h3>
            <button
              onClick={() => handleEditTestSet(null)}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
            >
              <Plus className="h-3.5 w-3.5" /> New Test Set
            </button>
          </div>

          {showTestSetForm && (
            <div className="rounded-lg border border-line bg-card p-4 space-y-3">
              <h4 className="text-sm font-medium text-primary">{editingTestSet ? "Edit Test Set" : "New Test Set"}</h4>
              <input
                value={testSetForm.name}
                onChange={(e) => setTestSetForm({ ...testSetForm, name: e.target.value })}
                placeholder="Test set name (e.g. Onboarding Q&A)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 outline-none transition"
              />
              <input
                value={testSetForm.description}
                onChange={(e) => setTestSetForm({ ...testSetForm, description: e.target.value })}
                placeholder="Description (optional)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 outline-none transition"
              />
              <div className="flex items-center gap-2">
                <button
                  onClick={handleSaveTestSet}
                  disabled={!testSetForm.name.trim()}
                  className="bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
                >
                  {editingTestSet ? "Update" : "Create"}
                </button>
                <button
                  onClick={() => setShowTestSetForm(false)}
                  className="border border-line/60 hover:bg-hover px-3 py-1.5 rounded-lg text-xs text-secondary transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {evalTestSets.length === 0 && !showTestSetForm ? (
            <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
              <p className="text-sm text-tertiary">No test sets yet.</p>
              <p className="text-xs text-tertiary mt-1">Create a test set to group related questions and expected answers.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {evalTestSets.map((ts) => (
                <div key={ts.id} className="rounded-lg border border-line overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-3 bg-canvas/50 hover:bg-hover/50 transition">
                    <div className="flex items-center gap-2 flex-1 cursor-pointer" onClick={() => toggleSet(ts.id)}>
                      {expandedSets.has(ts.id) ? (
                        <ChevronDown className="h-4 w-4 text-tertiary" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-tertiary" />
                      )}
                      <div>
                        <span className="text-sm font-medium text-secondary">{ts.name}</span>
                        {ts.description && (
                          <span className="text-xs text-tertiary ml-2">{ts.description}</span>
                        )}
                        <span className="text-xs text-tertiary ml-2">({ts.tests.length} tests)</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAddTest(ts.id)}
                        className="text-tertiary hover:text-brand transition text-xs flex items-center gap-1"
                        title="Add test"
                      >
                        <Plus className="h-3.5 w-3.5" /> Add Test
                      </button>
                      <button
                        onClick={() => handleEditTestSet(ts.id)}
                        className="text-tertiary hover:text-secondary transition"
                        title="Edit"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteTestSet(ts.id)}
                        className="text-tertiary hover:text-danger transition"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {expandedSets.has(ts.id) && (
                    <div className="border-t border-line">
                      {showTestForm === ts.id && (
                        <div className="px-4 py-3 bg-card space-y-2 border-b border-line">
                          <textarea
                            value={testForm.question}
                            onChange={(e) => setTestForm({ ...testForm, question: e.target.value })}
                            placeholder="Question"
                            rows={2}
                            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 outline-none transition resize-y"
                          />
                          <textarea
                            value={testForm.expected_answer}
                            onChange={(e) => setTestForm({ ...testForm, expected_answer: e.target.value })}
                            placeholder="Expected answer"
                            rows={2}
                            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 outline-none transition resize-y"
                          />
                          <div className="flex items-center gap-2">
                            <button
                              onClick={handleSaveTest}
                              disabled={!testForm.question.trim() || !testForm.expected_answer.trim()}
                              className="bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
                            >
                              {editingTest ? "Update" : "Add"}
                            </button>
                            <button
                              onClick={() => { setShowTestForm(null); setEditingTest(null); }}
                              className="border border-line/60 hover:bg-hover px-3 py-1.5 rounded-lg text-xs text-secondary transition"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}

                      {ts.tests.length === 0 && showTestForm !== ts.id ? (
                        <p className="px-4 py-3 text-xs text-tertiary">No tests in this set yet. Click "Add Test" to create one.</p>
                      ) : (
                        <div className="divide-y divide-line">
                          {ts.tests.map((t) => (
                            <div key={t.id} className="px-4 py-2.5 flex items-start justify-between hover:bg-hover/40 transition">
                              <div className="flex-1 min-w-0">
                                <p className="text-sm text-secondary">
                                  <span className="text-tertiary text-xs">Q:</span> {t.question}
                                </p>
                                <p className="text-sm text-secondary mt-0.5">
                                  <span className="text-tertiary text-xs">A:</span> {t.expected_answer}
                                </p>
                              </div>
                              <div className="flex items-center gap-2 ml-2 shrink-0">
                                <button
                                  onClick={() => handleEditTest(ts.id, t.id, t.question, t.expected_answer)}
                                  className="text-tertiary hover:text-secondary transition"
                                  title="Edit"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteTest(ts.id, t.id)}
                                  className="text-tertiary hover:text-danger transition"
                                  title="Delete"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : evalSubTab === "runs" ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-secondary">Evaluation Runs ({evalRuns.length})</h3>
            <button
              onClick={onLaunchRun}
              disabled={totalTests === 0}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
            >
              <Rocket className="h-3.5 w-3.5" /> Launch Run
            </button>
          </div>
          {evalRuns.length === 0 ? (
            <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
              <p className="text-sm text-tertiary">No evaluation runs yet.</p>
              <p className="text-xs text-tertiary mt-1">Launch a run to evaluate your agent against test sets.</p>
            </div>
          ) : (
            <div className="rounded-lg border border-line overflow-hidden">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
                  <tr>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Config</th>
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
                        <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                          r.config_source === "draft"
                            ? "bg-warning-soft text-warning"
                            : "bg-success-soft text-success"
                        }`}>
                          {r.config_source === "draft" ? "Draft" : "Published"}
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
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-secondary">Evaluation Schedules ({evalSchedules.length})</h3>
            <button
              onClick={() => handleEditSchedule(null)}
              disabled={evalTestSets.length === 0}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
            >
              <Plus className="h-3.5 w-3.5" /> New Schedule
            </button>
          </div>

          {showScheduleForm && (
            <div className="rounded-lg border border-line bg-card p-4 space-y-3">
              <h4 className="text-sm font-medium text-primary">{editingSchedule ? "Edit Schedule" : "New Schedule"}</h4>
              <input
                value={scheduleForm.name}
                onChange={(e) => setScheduleForm({ ...scheduleForm, name: e.target.value })}
                placeholder="Schedule name (e.g. Monthly HR Eval)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 outline-none transition"
              />
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-xs font-medium text-secondary">Repeat every</span>
                  <div className="flex gap-2 mt-1">
                    <input
                      type="number"
                      min={1}
                      value={scheduleForm.interval}
                      onChange={(e) => setScheduleForm({ ...scheduleForm, interval: parseInt(e.target.value) || 1 })}
                      className="w-20 bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 outline-none transition"
                    />
                    <select
                      value={scheduleForm.frequency}
                      onChange={(e) => setScheduleForm({ ...scheduleForm, frequency: e.target.value })}
                      className="flex-1 bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 outline-none transition"
                    >
                      {FREQUENCIES.map((f) => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                    </select>
                  </div>
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-xs font-medium text-secondary">Start date</span>
                  <input
                    type="datetime-local"
                    value={scheduleForm.start_date}
                    onChange={(e) => setScheduleForm({ ...scheduleForm, start_date: e.target.value })}
                    className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 outline-none transition"
                  />
                </label>
                <label className="block">
                  <span className="text-xs font-medium text-secondary">End date (optional)</span>
                  <input
                    type="datetime-local"
                    value={scheduleForm.end_date ?? ""}
                    onChange={(e) => setScheduleForm({ ...scheduleForm, end_date: e.target.value || null })}
                    className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 outline-none transition"
                  />
                </label>
              </div>
              <div>
                <label className="block text-xs font-medium text-secondary mb-1.5">Test sets to run</label>
                <div className="space-y-1.5 max-h-32 overflow-y-auto border border-line rounded-lg p-2 bg-canvas/70">
                  {evalTestSets.map((ts) => (
                    <label key={ts.id} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover/50 rounded px-1.5 py-1 transition">
                      <input
                        type="checkbox"
                        checked={scheduleForm.test_set_ids?.includes(ts.id) ?? false}
                        onChange={(e) => {
                          const ids = new Set(scheduleForm.test_set_ids ?? []);
                          if (e.target.checked) ids.add(ts.id);
                          else ids.delete(ts.id);
                          setScheduleForm({ ...scheduleForm, test_set_ids: Array.from(ids) });
                        }}
                        className="h-3.5 w-3.5 rounded border-line text-brand focus:ring-brand"
                      />
                      <span className="truncate">{ts.name} <span className="text-tertiary text-xs">({ts.tests.length})</span></span>
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-secondary">
                <input
                  type="checkbox"
                  checked={scheduleForm.enabled}
                  onChange={(e) => setScheduleForm({ ...scheduleForm, enabled: e.target.checked })}
                  className="h-3.5 w-3.5 rounded border-line text-brand focus:ring-brand"
                />
                Enabled
              </label>
              <div className="flex items-center gap-2 pt-1">
                <button
                  onClick={handleSaveSchedule}
                  className="bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-1.5 rounded-lg text-xs font-medium text-white transition"
                >
                  {editingSchedule ? "Update" : "Create"}
                </button>
                <button
                  onClick={() => setShowScheduleForm(false)}
                  className="border border-line/60 hover:bg-hover px-3 py-1.5 rounded-lg text-xs text-secondary transition"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {evalSchedules.length === 0 && !showScheduleForm ? (
            <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
              <Calendar className="h-8 w-8 text-tertiary mx-auto mb-2" />
              <p className="text-sm text-tertiary">No evaluation schedules yet.</p>
              <p className="text-xs text-tertiary mt-1">Schedule recurring evaluation runs with a simple frequency picker.</p>
            </div>
          ) : (
            evalSchedules.length > 0 && (
              <div className="rounded-lg border border-line overflow-hidden">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
                    <tr>
                      <th className="px-4 py-2 font-medium">Name</th>
                      <th className="px-4 py-2 font-medium">Frequency</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Last Run</th>
                      <th className="px-4 py-2 font-medium w-28"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {evalSchedules.map((s) => (
                      <tr key={s.id} className="hover:bg-hover/70 transition">
                        <td className="px-4 py-2.5 text-secondary font-medium">{s.name}</td>
                        <td className="px-4 py-2.5 text-secondary text-xs">{formatFrequency(s.frequency, s.interval)}</td>
                        <td className="px-4 py-2.5">
                          <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${
                            s.enabled ? "bg-success-soft text-success" : "bg-hover text-tertiary"
                          }`}>
                            {s.enabled ? "Active" : "Disabled"}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-tertiary text-xs">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {timeAgo(s.last_triggered_at)}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleToggleSchedule(s)}
                              className={`transition ${s.enabled ? "text-success hover:text-warning" : "text-tertiary hover:text-success"}`}
                              title={s.enabled ? "Disable" : "Enable"}
                            >
                              <Power className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleEditSchedule(s)}
                              className="text-tertiary hover:text-secondary transition"
                              title="Edit"
                            >
                              <Settings className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteSchedule(s)}
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
            )
          )}
        </div>
      )}
    </div>
  );
}
