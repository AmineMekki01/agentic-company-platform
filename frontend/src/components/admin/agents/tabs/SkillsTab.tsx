import { useState } from "react";
import { Plus, Pencil, Trash2, X, Save, Loader2, ExternalLink, Eye, Sparkles } from "lucide-react";
import type { Skill, SkillCreate } from "@/lib/api";

interface Props {
  agentSlug: string;
  agentSkills: Skill[];
  sharedSkills: Skill[];
  assignedSkillIds: Set<string>;
  loading: boolean;
  onCreateSkill: (body: SkillCreate) => Promise<void>;
  onUpdateSkill: (skillId: string, body: Partial<SkillCreate>) => Promise<void>;
  onDeleteSkill: (skillId: string) => Promise<void>;
  onToggleSkill: (skillId: string) => Promise<void>;
  onBatchAssign: (assign: string[], unassign: string[]) => Promise<void>;
}

export default function SkillsTab({
  agentSlug,
  agentSkills,
  sharedSkills,
  assignedSkillIds,
  loading,
  onCreateSkill,
  onUpdateSkill,
  onDeleteSkill,
  onToggleSkill,
  onBatchAssign,
}: Props) {
  const [editing, setEditing] = useState<Skill | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [viewing, setViewing] = useState<Skill | null>(null);
  const [form, setForm] = useState<SkillCreate>({ name: "", description: "", content: "" });
  const [saving, setSaving] = useState(false);
  const [pendingChecks, setPendingChecks] = useState<Set<string>>(new Set());
  const [pendingUnchecks, setPendingUnchecks] = useState<Set<string>>(new Set());
  const [batchSaving, setBatchSaving] = useState(false);

  const hasPendingChanges = pendingChecks.size > 0 || pendingUnchecks.size > 0;

  const isChecked = (skillId: string) => {
    if (pendingChecks.has(skillId)) return true;
    if (pendingUnchecks.has(skillId)) return false;
    return assignedSkillIds.has(skillId);
  };

  const toggleCheck = (skillId: string) => {
    const wasAssigned = assignedSkillIds.has(skillId);
    if (wasAssigned) {
      if (pendingUnchecks.has(skillId)) {
        setPendingUnchecks((prev) => {
          const next = new Set(prev);
          next.delete(skillId);
          return next;
        });
      } else {
        setPendingUnchecks((prev) => new Set([...prev, skillId]));
        setPendingChecks((prev) => {
          const next = new Set(prev);
          next.delete(skillId);
          return next;
        });
      }
    } else {
      if (pendingChecks.has(skillId)) {
        setPendingChecks((prev) => {
          const next = new Set(prev);
          next.delete(skillId);
          return next;
        });
      } else {
        setPendingChecks((prev) => new Set([...prev, skillId]));
        setPendingUnchecks((prev) => {
          const next = new Set(prev);
          next.delete(skillId);
          return next;
        });
      }
    }
  };

  const handleBatchSave = async () => {
    setBatchSaving(true);
    try {
      await onBatchAssign([...pendingChecks], [...pendingUnchecks]);
      setPendingChecks(new Set());
      setPendingUnchecks(new Set());
    } finally {
      setBatchSaving(false);
    }
  };

  const handleDiscardChanges = () => {
    setPendingChecks(new Set());
    setPendingUnchecks(new Set());
  };

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", description: "", content: "" });
    setShowEditor(true);
  };

  const openEdit = (skill: Skill) => {
    setViewing(null);
    setEditing(skill);
    setForm({ name: skill.name, description: skill.description, content: skill.content });
    setShowEditor(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.description.trim()) return;
    setSaving(true);
    try {
      if (editing) {
        await onUpdateSkill(editing.id, form);
      } else {
        await onCreateSkill({ ...form, scope: "agent", agent_slug: agentSlug });
      }
      setShowEditor(false);
      setEditing(null);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-tertiary">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Per-agent skills */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-xs font-medium text-secondary">Agent Skills</span>
            <p className="text-xs text-tertiary mt-0.5">Skills created specifically for this agent</p>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-1.5 text-xs bg-brand/10 hover:bg-brand/20 text-brand border border-brand/20 px-3 py-1.5 rounded-lg transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Create Skill
          </button>
        </div>

        {agentSkills.length === 0 ? (
          <div className="text-sm text-tertiary py-6 text-center border border-dashed border-line rounded-lg">
            No agent-specific skills yet. Create one to give this agent procedural instructions.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {agentSkills.map((skill) => (
              <div
                key={skill.id}
                className="group relative p-3 border border-line rounded-xl bg-card hover:border-brand/30 transition cursor-pointer"
                onClick={() => setViewing(skill)}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Sparkles className="h-3.5 w-3.5 text-brand shrink-0" />
                    <span className="text-sm font-medium text-primary truncate">{skill.name}</span>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onToggleSkill(skill.id); }}
                    className={`h-4 w-4 shrink-0 rounded border transition ${
                      skill.is_enabled
                        ? "bg-brand border-brand"
                        : "bg-canvas border-line hover:border-brand/50"
                    }`}
                  />
                </div>
                <p className="text-xs text-tertiary line-clamp-2">{skill.description}</p>
                {!skill.is_enabled && (
                  <span className="absolute top-2 right-8 text-[9px] uppercase tracking-wide text-tertiary bg-hover px-1.5 py-0.5 rounded">
                    Disabled
                  </span>
                )}
                <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition">
                  <span className="text-[10px] text-tertiary flex items-center gap-1">
                    <Eye className="h-3 w-3" /> Click to view
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Shared library skills */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <span className="text-xs font-medium text-secondary">Shared Library Skills</span>
            <p className="text-xs text-tertiary mt-0.5">Skills from the shared library — check to assign, then save</p>
          </div>
          <a
            href="/admin/skills"
            className="flex items-center gap-1 text-xs text-brand hover:underline"
          >
            Manage Library
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        {sharedSkills.length === 0 ? (
          <div className="text-sm text-tertiary py-6 text-center border border-dashed border-line rounded-lg">
            No shared skills available. Create skills in the shared library to assign them across agents.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {sharedSkills.map((skill) => {
                const checked = isChecked(skill.id);
                const isPending = pendingChecks.has(skill.id) || pendingUnchecks.has(skill.id);
                return (
                  <div
                    key={skill.id}
                    className={`group relative p-3 border rounded-xl bg-card cursor-pointer transition ${
                      isPending ? "border-brand/40 ring-1 ring-brand/20" : "border-line hover:border-brand/30"
                    } ${checked ? "border-brand/30" : ""}`}
                    onClick={() => setViewing(skill)}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <Sparkles className="h-3.5 w-3.5 text-brand shrink-0" />
                        <span className="text-sm font-medium text-primary truncate">{skill.name}</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCheck(skill.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 shrink-0 accent-brand cursor-pointer"
                      />
                    </div>
                    <p className="text-xs text-tertiary line-clamp-2">{skill.description}</p>
                    {isPending && (
                      <span className="absolute top-2 right-8 text-[9px] uppercase tracking-wide text-brand bg-brand/10 px-1.5 py-0.5 rounded">
                        Pending
                      </span>
                    )}
                    <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition">
                      <span className="text-[10px] text-tertiary flex items-center gap-1">
                        <Eye className="h-3 w-3" /> Click to view
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {hasPendingChanges && (
              <div className="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-line">
                <span className="text-xs text-tertiary mr-auto">
                  {pendingChecks.size + pendingUnchecks.size} pending change{pendingChecks.size + pendingUnchecks.size > 1 ? "s" : ""}
                </span>
                <button
                  onClick={handleDiscardChanges}
                  disabled={batchSaving}
                  className="px-3 py-1.5 text-xs border border-line rounded-lg hover:bg-hover transition"
                >
                  Discard
                </button>
                <button
                  onClick={handleBatchSave}
                  disabled={batchSaving}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
                >
                  {batchSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  {batchSaving ? "Saving…" : "Save Changes"}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Skill view popup */}
      {viewing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setViewing(null)}>
          <div
            className="bg-card border border-line rounded-xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-line">
              <div className="flex items-center gap-2 min-w-0">
                <Sparkles className="h-4 w-4 text-brand shrink-0" />
                <h3 className="font-semibold text-primary truncate">{viewing.name}</h3>
                {!viewing.is_enabled && (
                  <span className="text-[10px] uppercase tracking-wide text-tertiary bg-hover px-1.5 py-0.5 rounded shrink-0">Disabled</span>
                )}
              </div>
              <button onClick={() => setViewing(null)} className="p-1.5 rounded-lg hover:bg-hover text-tertiary shrink-0">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div>
                <span className="text-xs font-medium text-secondary">Description</span>
                <p className="text-sm text-primary mt-1">{viewing.description}</p>
              </div>
              {viewing.content && (
                <div>
                  <span className="text-xs font-medium text-secondary">Content</span>
                  <pre className="mt-1 text-xs font-mono text-secondary bg-canvas border border-line rounded-lg p-3 overflow-x-auto whitespace-pre-wrap max-h-60 overflow-y-auto">
                    {viewing.content}
                  </pre>
                </div>
              )}
            </div>
            {agentSkills.some((s) => s.id === viewing.id) && (
              <div className="flex justify-end gap-2 px-5 py-4 border-t border-line">
                <button
                  onClick={() => {
                    if (confirm(`Delete skill "${viewing.name}"?`)) {
                      onDeleteSkill(viewing.id);
                      setViewing(null);
                    }
                  }}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm border border-danger/30 text-danger rounded-lg hover:bg-danger-soft transition"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
                <button
                  onClick={() => openEdit(viewing)}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Skill editor modal */}
      {showEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowEditor(false)}>
          <div
            className="bg-card border border-line rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-line">
              <h3 className="font-semibold text-primary">{editing ? "Edit Skill" : "Create Skill"}</h3>
              <button onClick={() => setShowEditor(false)} className="p-1.5 rounded-lg hover:bg-hover text-tertiary">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-secondary mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. jira-triage"
                  className="w-full px-3 py-2 text-sm bg-canvas border border-line rounded-lg focus:outline-none focus:border-brand"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-secondary mb-1">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="When to use this skill. Be specific so the agent can match it to user requests."
                  rows={2}
                  className="w-full px-3 py-2 text-sm bg-canvas border border-line rounded-lg focus:outline-none focus:border-brand resize-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-secondary mb-1">Content (SKILL.md)</label>
                <textarea
                  value={form.content}
                  onChange={(e) => setForm({ ...form, content: e.target.value })}
                  placeholder={"# skill-name\n\n## Instructions\n1. Step one\n2. Step two\n..."}
                  rows={12}
                  className="w-full px-3 py-2 text-sm font-mono bg-canvas border border-line rounded-lg focus:outline-none focus:border-brand resize-y"
                />
                <p className="text-xs text-tertiary mt-1">
                  Markdown instructions the agent reads when it activates this skill.
                </p>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-line">
              <button
                onClick={() => setShowEditor(false)}
                className="px-4 py-2 text-sm border border-line rounded-lg hover:bg-hover transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !form.name.trim() || !form.description.trim()}
                className="flex items-center gap-1.5 px-4 py-2 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {saving ? "Saving…" : "Save Skill"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
