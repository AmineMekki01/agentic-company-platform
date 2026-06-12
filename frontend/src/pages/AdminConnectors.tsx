import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api, type Connector, type ConnectorCreate } from "@/lib/api";
import ServiceIcon from "@/components/ServiceIcon";

function ConnectorBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    notion: "bg-indigo-500/15 text-indigo-400",
    jira: "bg-blue-500/15 text-blue-400",
    s3: "bg-amber-500/15 text-amber-400",
    sharepoint: "bg-emerald-500/15 text-emerald-400",
  };
  return (
    <span
      className={
        "text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 " +
        (colors[type.toLowerCase()] || "bg-neutral-700 text-neutral-400")
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
    await api.createConnector(form);
    setShowForm(false);
    setForm({ slug: "", name: "", connector_type: "notion", credentials: { token: "" } });
    refresh();
  };

  const remove = async (slug: string) => {
    if (!confirm("Delete this connector credential? Any linked knowledge sources will be orphaned.")) return;
    await api.deleteConnector(slug);
    refresh();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Connector Credentials</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setShowForm((s) => !s)}
            className="text-sm bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded-md"
          >
            {showForm ? "Cancel" : "Add Credential"}
          </button>
          <button
            onClick={refresh}
            className="text-sm bg-neutral-800 hover:bg-neutral-700 px-3 py-1.5 rounded-md"
          >
            Refresh
          </button>
        </div>
      </div>

      <p className="text-sm text-neutral-400 mb-4">
        Store API credentials for external services. Knowledge sources reference these credentials to sync data.
      </p>

      {showForm && (
        <div className="bg-neutral-800/60 rounded-lg p-4 mb-4 space-y-2 max-w-lg">
          <h2 className="font-medium mb-2">New Connector Credential</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. notion-main-workspace)"
            className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
            className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
          />
          <select
            value={form.connector_type}
            onChange={(e) => setForm({ ...form, connector_type: e.target.value })}
            className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
          >
            <option value="notion">Notion</option>
            <option value="jira">Jira</option>
            <option value="s3">S3</option>
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
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).email || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, email: e.target.value } })
                }
                placeholder="Jira Email"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).api_token || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, api_token: e.target.value } })
                }
                placeholder="Jira API Token"
                type="password"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).project_key || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, project_key: e.target.value } })
                }
                placeholder="Default Project Key (e.g. IT)"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
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
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).secret_key || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, secret_key: e.target.value } })
                }
                placeholder="AWS Secret Access Key"
                type="password"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).region || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, region: e.target.value } })
                }
                placeholder="Region (default: us-east-1)"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
              />
              <input
                value={String((form.credentials as Record<string, string>).endpoint_url || "")}
                onChange={(e) =>
                  setForm({ ...form, credentials: { ...form.credentials, endpoint_url: e.target.value } })
                }
                placeholder="Endpoint URL (optional, for MinIO / DigitalOcean Spaces)"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
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
              className="w-full bg-neutral-900 border border-neutral-700 rounded-md px-3 py-2 text-sm"
            />
          )}
          <button
            onClick={create}
            className="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-md text-sm font-medium"
          >
            Save Credential
          </button>
        </div>
      )}

      {loading && <p className="text-neutral-400 text-sm">Loading…</p>}
      <div className="space-y-2">
        {connectors.map((c) => (
          <div
            key={c.id}
            className="flex items-center justify-between bg-neutral-800/60 rounded-lg px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-neutral-900/80 border border-neutral-700/50">
                <ServiceIcon type={c.connector_type} size={22} />
              </div>
              <div>
                <div className="font-medium flex items-center gap-2">
                  {c.name}
                  <ConnectorBadge type={c.connector_type} />
                </div>
                <div className="text-xs text-neutral-400">{c.slug}</div>
              </div>
            </div>
            <button
              onClick={() => remove(c.slug)}
              className="text-sm text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-md px-2 py-1 transition"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        {!loading && connectors.length === 0 && (
          <p className="text-neutral-400 text-sm">No connector credentials configured.</p>
        )}
      </div>
    </div>
  );
}
