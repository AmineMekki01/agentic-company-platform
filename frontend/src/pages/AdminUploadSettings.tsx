import { useEffect, useState } from "react";
import { HardDrive, Save } from "lucide-react";
import { api, type Connector, type UploadSettings } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

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
      <div className="flex h-full items-center justify-center text-secondary">
        <HardDrive className="mr-2 h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  if (!settings) {
    return <div className="text-danger">{error || "Unable to load settings"}</div>;
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
      <AdminPageHeader
        title="Upload Settings"
        description="Configure where uploaded chat files are stored and how long they are retained"
        icon={HardDrive}
        iconColor="text-success"
        iconBg="bg-success-soft"
      />

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="rounded-2xl border border-line/60 bg-card p-5 shadow-sm backdrop-blur-sm transition hover:border-line/60">
          <label className="flex cursor-pointer items-center gap-3">
            <input
              type="checkbox"
              checked={settings.enabled}
              onChange={(e) =>
                setSettings((s) => (s ? { ...s, enabled: e.target.checked } : s))
              }
              className="h-4 w-4 rounded border-line bg-hover text-brand focus:ring-brand"
            />
            <div>
              <span className="block text-sm font-medium text-primary">Enable file uploads</span>
              <span className="block text-xs text-tertiary">
                Allow users to attach files to chat messages
              </span>
            </div>
          </label>
        </div>

        <div className="rounded-2xl border border-line/60 bg-card p-5 space-y-4 shadow-sm backdrop-blur-sm transition hover:border-line/60">
          <h2 className="text-sm font-semibold text-primary">S3 Destination</h2>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary">
              S3 Connector
            </label>
            <select
              value={settings.s3_connector_id ?? ""}
              onChange={(e) =>
                setSettings((s) =>
                  s ? { ...s, s3_connector_id: e.target.value || null } : s
                )
              }
              className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
            >
              <option value="">— Select S3 connector —</option>
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.slug})
                </option>
              ))}
            </select>
            {connectors.length === 0 && (
              <p className="mt-1 text-xs text-danger">
                No S3 connectors configured. Create one in Connectors first.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-secondary">Bucket</label>
              <input
                type="text"
                value={settings.s3_bucket}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, s3_bucket: e.target.value } : s))
                }
                placeholder="my-company-bucket"
                className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-secondary">
                Base Prefix
              </label>
              <input
                type="text"
                value={settings.s3_base_prefix}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, s3_base_prefix: e.target.value } : s))
                }
                placeholder="uploads/"
                className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-line/60 bg-card p-5 space-y-4 shadow-sm backdrop-blur-sm transition hover:border-line/60">
          <h2 className="text-sm font-semibold text-primary">Policy</h2>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-secondary">
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
                className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
              <p className="mt-1 text-[11px] text-tertiary">0 = keep forever</p>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-secondary">
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
                className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-secondary">
                Encryption
              </label>
              <select
                value={settings.encryption}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, encryption: e.target.value } : s))
                }
                className="w-full rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
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
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-brand to-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 shadow-lg shadow-brand/15"
          >
            <Save className="h-4 w-4" />
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
