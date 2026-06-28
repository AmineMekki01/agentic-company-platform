import { useEffect, useState, useCallback } from "react";
import { Sparkles, Plus, Pencil, Trash2, X, Save, Loader2, Eye } from "lucide-react";
import { api, type Skill, type SkillCreate } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

export default function AdminSkills() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showEditor, setShowEditor] = useState(false);
  const [editing, setEditing] = useState<Skill | null>(null);
  const [viewing, setViewing] = useState<Skill | null>(null);
  const [form, setForm] = useState<SkillCreate>({ name: "", description: "", content: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const all = await api.listAllSkills();
      setSkills(all.filter((s) => s.scope === "shared"));
    } catch {
      setError("Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
        await api.updateSkill(editing.id, form);
      } else {
        await api.createSkill({ ...form, scope: "shared" });
      }
      setShowEditor(false);
      setEditing(null);
      await load();
    } catch {
      setError("Failed to save skill");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.deleteSkill(id);
    await load();
  };

  return (
    <div>
      <AdminPageHeader
        title="Skills Library"
        description="Shared skills that can be assigned to any agent. Skills are markdown instructions agents read on-demand."
        icon={Sparkles}
      >
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 text-white px-4 py-2 rounded-lg font-medium transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-4 w-4" />
          New Skill
        </button>
      </AdminPageHeader>

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12 text-tertiary">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : skills.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-line rounded-xl">
          <Sparkles className="h-8 w-8 text-tertiary mx-auto mb-3" />
          <p className="text-sm text-tertiary">No shared skills yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {skills.map((skill) => (
            <div
              key={skill.id}
              className="group relative p-4 border border-line rounded-xl bg-card hover:border-brand/30 transition cursor-pointer"
              onClick={() => setViewing(skill)}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Sparkles className="h-4 w-4 text-brand shrink-0" />
                  <span className="font-medium text-primary truncate">{skill.name}</span>
                </div>
                {!skill.is_enabled && (
                  <span className="text-[9px] uppercase tracking-wide text-tertiary bg-hover px-1.5 py-0.5 rounded shrink-0">
                    Disabled
                  </span>
                )}
              </div>
              <p className="text-sm text-tertiary line-clamp-2">{skill.description}</p>
              <div className="flex items-center gap-1 mt-3 opacity-0 group-hover:opacity-100 transition">
                <span className="text-[10px] text-tertiary flex items-center gap-1">
                  <Eye className="h-3 w-3" /> Click to view
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

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
            <div className="flex justify-end gap-2 px-5 py-4 border-t border-line">
              <button
                onClick={() => {
                  if (confirm(`Delete skill "${viewing.name}"? This removes it from all assigned agents.`)) {
                    handleDelete(viewing.id);
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
          </div>
        </div>
      )}

      {showEditor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowEditor(false)}>
          <div
            className="bg-card border border-line rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-line">
              <h3 className="font-semibold text-primary">{editing ? "Edit Skill" : "New Shared Skill"}</h3>
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
