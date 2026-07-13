import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, Loader2, Plus, RefreshCw, Save, Trash2, Plug } from "lucide-react";
import { api, type Connector, type ConnectorCreate, type Secret } from "@/lib/api";
import ServiceIcon from "@/components/ServiceIcon";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

function ConnectorBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    notion: "bg-brand/10 text-brand border-brand/20",
    jira: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    s3: "bg-warning-soft text-warning border-warning/20",
    gdrive: "bg-green-500/10 text-green-400 border-green-500/20",
  };
  return (
    <span
      className={
        "text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border " +
        (colors[type.toLowerCase()] || "bg-hover text-secondary border-line")
      }
    >
      {type}
    </span>
  );
}

const inputClass =
  "w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition";

export default function AdminConnectors() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [secrets, setSecrets] = useState<Secret[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ConnectorCreate>({
    slug: "",
    name: "",
    connector_type: "notion",
    secret_id: "",
  });
  const [projectKey, setProjectKey] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      const [conns, secs] = await Promise.all([api.listConnectors(), api.listSecrets()]);
      setConnectors(conns);
      setSecrets(secs);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const matchingSecrets = secrets.filter((s) => s.secret_type === form.connector_type);

  const create = async () => {
    if (!form.slug.trim() || !form.name.trim() || !form.secret_id) return;
    setSaving(true);
    setError(null);
    try {
      const body: ConnectorCreate = { ...form };
      if (form.connector_type === "jira" && projectKey.trim()) {
        body.config = { project_key: projectKey.trim() };
      }
      await api.createConnector(body);
      setShowForm(false);
      setForm({ slug: "", name: "", connector_type: "notion", secret_id: "" });
      setProjectKey("");
      await refresh();
    } catch (e: any) {
      setError(e.message || "Failed to create connector");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (slug: string) => {
    if (!confirm("Delete this connector? Any linked knowledge sources will be orphaned.")) return;
    setError(null);
    try {
      await api.deleteConnector(slug);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Failed to delete connector");
    }
  };

  return (
    <div>
      <AdminPageHeader
        title="Connectors"
        description="Wire a secret to a specific integration"
        icon={Plug}
        iconColor="text-sky-400"
        iconBg="bg-sky-500/10"
      >
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? "Cancel" : "Add Connector"}
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger-soft text-danger text-sm px-4 py-2.5 mb-4">
          {error}
        </div>
      )}

      {showForm && (
        <div className="rounded-2xl border border-line/60 bg-card p-5 mb-6 space-y-3 max-w-lg shadow-sm backdrop-blur-sm transition hover:border-line/60">
          <h2 className="font-medium text-primary">New Connector</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. notion-main-workspace)"
            className={inputClass}
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
            className={inputClass}
          />
          <select
            value={form.connector_type}
            onChange={(e) => setForm({ ...form, connector_type: e.target.value, secret_id: "" })}
            className={inputClass}
          >
            <option value="notion">Notion</option>
            <option value="jira">Jira</option>
            <option value="s3">S3</option>
            <option value="gdrive">Google Drive</option>
          </select>

          {matchingSecrets.length === 0 ? (
            <div className="rounded-lg border border-dashed border-line px-3 py-2.5 text-sm text-tertiary">
              No {form.connector_type} secrets yet.{" "}
              <Link to="/admin/secrets" className="inline-flex items-center gap-1 text-brand hover:underline">
                Create one <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          ) : (
            <select
              value={form.secret_id}
              onChange={(e) => setForm({ ...form, secret_id: e.target.value })}
              className={inputClass}
            >
              <option value="">Select a secret…</option>
              {matchingSecrets.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          )}

          {form.connector_type === "jira" && (
            <input
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              placeholder="Default Project Key (e.g. IT) — optional"
              className={inputClass}
            />
          )}

          <button
            onClick={create}
            disabled={saving || !form.secret_id}
            className="flex items-center gap-1.5 bg-success hover:bg-success-hover disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-success/15"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Connector
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-tertiary text-sm py-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading connectors…
        </div>
      )}
      <div className="space-y-2">
        {connectors.map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between bg-card border border-line rounded-xl px-4 py-3 transition hover:border-line"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-canvas border border-line">
                <ServiceIcon type={c.connector_type} size={22} />
              </div>
              <div>
                <div className="font-medium text-primary flex items-center gap-2">
                  {c.name}
                  <ConnectorBadge type={c.connector_type} />
                </div>
                <div className="text-xs text-tertiary">
                  {c.slug}
                  {c.secret_name && <> · secret: {c.secret_name}</>}
                </div>
              </div>
            </div>
            <button
              onClick={() => remove(c.slug)}
              className="rounded-md p-2 text-tertiary hover:text-danger hover:bg-danger-soft transition"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {!loading && connectors.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-tertiary">
            <Plug className="h-10 w-10 text-tertiary mb-3" />
            <p className="text-sm">No connectors configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
