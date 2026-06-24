import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Save, Trash2, Plug } from "lucide-react";
import { api, type Connector, type ConnectorCreate } from "@/lib/api";
import ServiceIcon from "@/components/ServiceIcon";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

function ConnectorBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    notion: "bg-brand/10 text-brand border-brand/20",
    jira: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    s3: "bg-warning-soft text-warning border-warning/20",
    sharepoint: "bg-success-soft text-success border-success/20",
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

export default function AdminConnectors() {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ConnectorCreate>({
    slug: "",
    name: "",
    connector_type: "notion",
    credentials: { token: "" },
  });

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.listConnectors();
      setConnectors(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const create = async () => {
    if (!form.slug.trim() || !form.name.trim()) return;
    setSaving(true);
    try {
      await api.createConnector(form);
      setShowForm(false);
      setForm({ slug: "", name: "", connector_type: "notion", credentials: { token: "" } });
      await refresh();
    } finally {
      setSaving(false);
    }
  };

  const remove = async (slug: string) => {
    if (!confirm("Delete this connector credential? Any linked knowledge sources will be orphaned.")) return;
    await api.deleteConnector(slug);
    refresh();
  };

  return (
    <div>
      <AdminPageHeader
        title="Connector Credentials"
        description="Store API credentials for external services"
        icon={Plug}
        iconColor="text-sky-400"
        iconBg="bg-sky-500/10"
      >
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? "Cancel" : "Add Credential"}
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {showForm && (
        <div className="rounded-2xl border border-line/60 bg-card p-5 mb-6 space-y-3 max-w-lg shadow-sm backdrop-blur-sm transition hover:border-line/60">
          <h2 className="font-medium text-primary">New Connector Credential</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. notion-main-workspace)"
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          />
          <select
            value={form.connector_type}
            onChange={(e) => setForm({ ...form, connector_type: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          >
            <option value="notion">Notion</option>
            <option value="jira">Jira</option>
            <option value="s3">S3</option>
            <option value="gdrive">Google Drive</option>
            <option value="sharepoint">SharePoint (coming soon)</option>
          </select>
          {form.connector_type === "jira" && (
            <>
              <input
                value={String((form.credentials as Record<string, string>).base_url || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, base_url: e.target.value } })
                }
                placeholder="Jira Base URL (e.g. https://your-domain.atlassian.net)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).email || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, email: e.target.value } })
                }
                placeholder="Jira Email"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).api_token || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, api_token: e.target.value } })
                }
                placeholder="Jira API Token"
                type="password"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).project_key || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, project_key: e.target.value } })
                }
                placeholder="Default Project Key (e.g. IT)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </>
          )}
          {form.connector_type === "s3" && (
            <>
              <input
                value={String((form.credentials as Record<string, string>).access_key || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, access_key: e.target.value } })
                }
                placeholder="AWS Access Key ID"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).secret_key || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, secret_key: e.target.value } })
                }
                placeholder="AWS Secret Access Key"
                type="password"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).region || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, region: e.target.value } })
                }
                placeholder="Region (default: us-east-1)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={String((form.credentials as Record<string, string>).endpoint_url || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, endpoint_url: e.target.value } })
                }
                placeholder="Endpoint URL (optional, for MinIO / DigitalOcean Spaces)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </>
          )}
          {form.connector_type === "notion" && (
            <input
              value={String((form.credentials as Record<string, string>).token || "")}
              onChange={(e) =>
                setForm({ ...form, credentials: { ...form.credentials, token: e.target.value } })
              }
              placeholder="Notion Integration Token"
              type="password"
              className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
            />
          )}
          {form.connector_type === "gdrive" && (
            <>
              <textarea
                value={String((form.credentials as Record<string, string>).service_account_json || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, service_account_json: e.target.value } })
                }
                placeholder="Paste Service Account JSON key here"
                rows={6}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition font-mono"
              />
              <input
                value={String((form.credentials as Record<string, string>).delegated_user || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, delegated_user: e.target.value } })
                }
                placeholder="Delegated user email (optional, for domain-wide delegation)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </>
          )}
          <button
            onClick={create}
            disabled={saving}
            className="flex items-center gap-1.5 bg-success hover:bg-success-hover disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-success/15"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Credential
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
                <div className="text-xs text-tertiary">{c.slug}</div>
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
            <p className="text-sm">No connector credentials configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
