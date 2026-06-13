import { useEffect, useState } from "react";
import { HardDrive, Save } from "lucide-react";
import { api, type Connector, type UploadSettings } from "@/lib/api";

export default function AdminUploadSettings() {
  const [settings, setSettings] = useState<UploadSettings | null>(null);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.getUploadSettings(),
      api.listConnectors(),
    ])
      .then(([s, c]) => {
        setSettings(s);
        setConnectors(c.filter((x) => x.connector_type === "s3"));
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load settings");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-zinc-400">
        <HardDrive className="mr-2 h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  if (!settings) {
    return <div className="text-red-400">{error || "Unable to load settings"}</div>;
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError("");
    try {
      const updated = await api.updateUploadSettings({
        enabled: settings.enabled,
        s3_connector_id: settings.s3_connector_id,
        s3_bucket: settings.s3_bucket,
        s3_base_prefix: settings.s3_base_prefix,
        retention_days: settings.retention_days,
        max_file_size_mb: settings.max_file_size_mb,
        encryption: settings.encryption,
      });
      setSettings(updated);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Save failed";
      setError(detail);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-xl font-semibold text-zinc-100">Upload Settings</h1>
      <p className="mb-6 text-sm text-zinc-500">
        Configure where uploaded chat files are stored and how long they are retained.
      </p>

      {error && (
        <div className="mb-4 rounded-lg border border-red-800 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <label className="flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(e) =>
                setSettings((s) => (s ? { ...s, enabled: e.target.checked } : s))
              }
              className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-600 focus:ring-indigo-500"
            />
            <div>
              <span className="block text-sm font-medium text-zinc-200">Enable file uploads</span>
              <span className="block text-xs text-zinc-500">
                Allow users to attach files to chat messages
              </span>
            </div>
          </label>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-200">S3 Destination</h2>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-zinc-400">
              S3 Connector
            </label>
            <select
              value={settings.s3_connector_id ?? ""}
              onChange={(e) =>
                setSettings((s) =>
                  s ? { ...s, s3_connector_id: e.target.value || null } : s
                )
              }
              className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
            >
              <option value="">— Select S3 connector —</option>
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.slug})
                </option>
              ))}
            </select>
            {connectors.length === 0 && (
              <p className="mt-1 text-xs text-red-400">
                No S3 connectors configured. Create one in Connectors first.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">Bucket</label>
              <input
                type="text"
                value={settings.s3_bucket}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, s3_bucket: e.target.value } : s))
                }
                placeholder="my-company-bucket"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Base Prefix
              </label>
              <input
                type="text"
                value={settings.s3_base_prefix}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, s3_base_prefix: e.target.value } : s))
                }
                placeholder="uploads/"
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-200">Policy</h2>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Retention (days)
              </label>
              <input
                type="number"
                min={0}
                max={365}
                value={settings.retention_days}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, retention_days: parseInt(e.target.value, 10) || 0 } : s
                  )
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
              />
              <p className="mt-1 text-[11px] text-zinc-600">0 = keep forever</p>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Max File Size (MB)
              </label>
              <input
                type="number"
                min={1}
                max={500}
                value={settings.max_file_size_mb}
                onChange={(e) =>
                  setSettings((s) =>
                    s ? { ...s, max_file_size_mb: parseInt(e.target.value, 10) || 50 } : s
                  )
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-400">
                Encryption
              </label>
              <select
                value={settings.encryption}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, encryption: e.target.value } : s))
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-indigo-500"
              >
                <option value="AES256">SSE-S3 (AES256)</option>
                <option value="aws:kms">SSE-KMS</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
