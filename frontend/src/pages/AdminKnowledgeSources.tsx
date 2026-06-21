import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2, BookOpen } from "lucide-react";
import {
  api,
  type Connector,
  type KnowledgeSource,
  type KnowledgeSourceCreate,
  type NotionResource,
  type S3Bucket,
} from "@/lib/api";
import ServiceIcon from "@/components/ServiceIcon";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    syncing: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    pending: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
    error: "bg-red-500/10 text-red-400 border-red-500/20",
  };
  return (
    <span className={`text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border ${styles[status] || styles.pending}`}>
      {status}
    </span>
  );
}

function SourceBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    notion: "bg-indigo-500/10 text-indigo-400 border-indigo-500/20",
    s3: "bg-sky-500/10 text-sky-400 border-sky-500/20",
  };
  return (
    <span className={`text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border ${styles[type] || "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
      {type}
    </span>
  );
}

export default function AdminKnowledgeSources() {
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<KnowledgeSourceCreate>({
    slug: "",
    name: "",
    source_type: "notion",
    config: {},
    connector_id: null,
  });

  // Notion browse state
  const [browseMode, setBrowseMode] = useState<"database" | "page">("database");
  const [browseItems, setBrowseItems] = useState<NotionResource[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseAttempted, setBrowseAttempted] = useState(false);
  const [selectedItem, setSelectedItem] = useState<NotionResource | null>(null);

  // S3 browse state
  const [s3Buckets, setS3Buckets] = useState<S3Bucket[]>([]);
  const [s3BrowseLoading, setS3BrowseLoading] = useState(false);
  const [s3BrowseAttempted, setS3BrowseAttempted] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const [sourceData, connData] = await Promise.all([
        api.listKnowledgeSources(),
        api.listConnectors(),
      ]);
      setSources(sourceData);
      setConnectors(connData);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const create = async () => {
    if (!form.slug.trim() || !form.name.trim()) return;
    await api.createKnowledgeSource(form);
    setShowForm(false);
    setForm({ slug: "", name: "", source_type: "notion", config: {}, connector_id: null });
    setBrowseItems([]);
    setSelectedItem(null);
    refresh();
  };

  const remove = async (slug: string) => {
    if (!confirm("Delete this knowledge source?")) return;
    try {
      await api.deleteKnowledgeSource(slug);
    } catch (e: any) {
      alert(`Delete failed: ${e.message}`);
    }
    refresh();
  };

  const [syncingSlugs, setSyncingSlugs] = useState<Set<string>>(new Set());

  const triggerSync = async (slug: string) => {
    setSyncingSlugs((prev) => new Set(prev).add(slug));
    try {
      await api.syncKnowledgeSource(slug);
      // Poll for completion
      const poll = setInterval(async () => {
        const sources = await api.listKnowledgeSources();
        const s = sources.find((x) => x.slug === slug);
        if (s && s.status !== "syncing" && s.status !== "pending") {
          clearInterval(poll);
          setSyncingSlugs((prev) => {
            const next = new Set(prev);
            next.delete(slug);
            return next;
          });
          setSources(sources);
        }
      }, 3000);
      // Safety: stop polling after 2 minutes
      setTimeout(() => clearInterval(poll), 120_000);
    } catch (e: any) {
      alert(`Sync failed: ${e.message}`);
      setSyncingSlugs((prev) => {
        const next = new Set(prev);
        next.delete(slug);
        return next;
      });
    }
  };

  const browseNotion = async () => {
    if (!form.connector_id) return;
    const conn = connectors.find((c) => c.id === form.connector_id);
    if (!conn) return;
    setBrowseLoading(true);
    setBrowseAttempted(true);
    try {
      const items =
        browseMode === "database"
          ? await api.listNotionDatabases(conn.slug)
          : await api.listNotionPages(conn.slug);
      setBrowseItems(items);
    } catch (e: any) {
      alert(`Browse failed: ${e.message}`);
    } finally {
      setBrowseLoading(false);
    }
  };

  const selectItem = (item: NotionResource) => {
    setSelectedItem(item);
    if (browseMode === "database") {
      setForm({
        ...form,
        name: item.name,
        config: { ...form.config, database_id: item.id },
      });
    } else {
      setForm({
        ...form,
        name: item.name,
        config: { ...form.config, page_id: item.id, page_title: item.name },
      });
    }
  };

  const browseS3 = async () => {
    if (!form.connector_id) return;
    const conn = connectors.find((c) => c.id === form.connector_id);
    if (!conn) return;
    setS3BrowseLoading(true);
    setS3BrowseAttempted(true);
    try {
      const buckets = await api.listS3Buckets(conn.slug);
      setS3Buckets(buckets);
    } catch (e: any) {
      alert(`Browse failed: ${e.message}`);
    } finally {
      setS3BrowseLoading(false);
    }
  };

  const connectorOptions = connectors.filter((c) => {
    if (form.source_type === "notion") return c.connector_type === "notion";
    if (form.source_type === "s3") return c.connector_type === "s3";
    return true;
  });

  return (
    <div>
      <AdminPageHeader
        title="Knowledge Sources"
        description="Manage data sources for agent retrieval"
        icon={BookOpen}
        iconColor="text-amber-400"
        iconBg="bg-amber-500/10"
      >
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 px-3 py-2 rounded-lg font-medium transition shadow-lg shadow-indigo-500/15"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? "Cancel" : "Add Source"}
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-zinc-900/60 hover:bg-zinc-800/60 border border-zinc-800/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {showForm && (
        <div className="rounded-2xl border border-zinc-800/60 bg-zinc-900/40 p-5 mb-6 space-y-3 max-w-lg shadow-sm backdrop-blur-sm transition hover:border-zinc-700/60">
          <h2 className="font-medium text-zinc-200">New Knowledge Source</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. notion-hr)"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          />
          <select
            value={form.source_type}
            onChange={(e) => {
              const type = e.target.value;
              setForm({
                slug: form.slug,
                name: form.name,
                source_type: type,
                config: {},
                connector_id: null,
              });
              setBrowseItems([]);
              setSelectedItem(null);
              setBrowseAttempted(false);
              setS3Buckets([]);
              setS3BrowseAttempted(false);
            }}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          >
            <option value="notion">Notion</option>
            <option value="s3">S3 Bucket</option>
          </select>

          {/* Connector selector */}
          <select
            value={form.connector_id || ""}
            onChange={(e) => {
              setForm({ ...form, connector_id: e.target.value || null });
              setS3Buckets([]);
              setS3BrowseAttempted(false);
            }}
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
          >
            <option value="">Select connector credential…</option>
            {connectorOptions.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.slug})
              </option>
            ))}
          </select>

          {/* Notion browse */}
          {form.source_type === "notion" && form.connector_id && (
            <div className="space-y-2">
              <div className="flex gap-2 items-center">
                <select
                  value={browseMode}
                  onChange={(e) => {
                    setBrowseMode(e.target.value as "database" | "page");
                    setBrowseItems([]);
                    setSelectedItem(null);
                  }}
                  className="bg-zinc-950 border border-zinc-800 rounded-lg px-2 py-1.5 text-sm text-zinc-200 focus:border-indigo-500/50 outline-none transition"
                >
                  <option value="database">Browse Databases</option>
                  <option value="page">Browse Pages</option>
                </select>
                <button
                  onClick={browseNotion}
                  disabled={browseLoading}
                  className="text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg transition"
                >
                  {browseLoading ? "Browsing…" : "Browse Notion"}
                </button>
              </div>

              {browseItems.length > 0 && (
                <div className="border border-zinc-800 rounded-lg p-2 space-y-1 max-h-40 overflow-y-auto bg-zinc-950">
                  <div className="text-xs text-zinc-500 mb-1">
                    Select a {browseMode === "database" ? "database" : "page"}:
                  </div>
                  {browseItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => selectItem(item)}
                      className={`w-full text-left px-2 py-1 rounded-md text-sm transition ${
                        selectedItem?.id === item.id
                          ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                          : "hover:bg-zinc-800 text-zinc-300"
                      }`}
                    >
                      {item.name}{" "}
                      <span className="text-xs text-zinc-500">({item.id})</span>
                    </button>
                  ))}
                </div>
              )}

              {!browseLoading && browseAttempted && browseItems.length === 0 && (
                <p className="text-xs text-amber-400">
                  No {browseMode === "database" ? "databases" : "pages"} found. Make sure your Notion integration token is correct and the content is shared with the integration.
                </p>
              )}

              {selectedItem && (
                <div className="text-xs text-emerald-400">
                  Selected: {selectedItem.name} ({selectedItem.id})
                </div>
              )}

              <input
                value={
                  (form.config?.database_id as string) ||
                  (form.config?.page_id as string) ||
                  ""
                }
                onChange={(e) => {
                  const val = e.target.value;
                  if (browseMode === "database") {
                    setForm({ ...form, config: { ...form.config, database_id: val, page_id: undefined } });
                  } else {
                    setForm({ ...form, config: { ...form.config, page_id: val, database_id: undefined } });
                  }
                }}
                placeholder={`Notion ${browseMode === "database" ? "Database" : "Page"} ID (or pick above)`}
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
              />
            </div>
          )}

          {/* S3 bucket + prefix */}
          {form.source_type === "s3" && form.connector_id && (
            <div className="space-y-2">
              <div className="flex gap-2 items-center">
                <button
                  onClick={browseS3}
                  disabled={s3BrowseLoading}
                  className="text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg transition"
                >
                  {s3BrowseLoading ? "Loading…" : "List Buckets"}
                </button>
              </div>

              {s3Buckets.length > 0 && (
                <select
                  value={(form.config?.bucket as string) || ""}
                  onChange={(e) =>
                    setForm({ ...form, config: { ...form.config, bucket: e.target.value } })
                  }
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
                >
                  <option value="">Select bucket…</option>
                  {s3Buckets.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
                </select>
              )}

              {!s3BrowseLoading && s3BrowseAttempted && s3Buckets.length === 0 && (
                <p className="text-xs text-amber-400">
                  No buckets found. Check your S3 connector credentials.
                </p>
              )}

              <input
                value={(form.config?.bucket as string) || ""}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, bucket: e.target.value } })
                }
                placeholder="Or enter bucket name manually"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
              />
              <input
                value={(form.config?.prefix as string) || ""}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, prefix: e.target.value } })
                }
                placeholder="Folder prefix (optional, e.g. docs/hr/)"
                className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/10 outline-none transition"
              />
            </div>
          )}

          {form.source_type === "notion" && !form.connector_id && (
            <p className="text-xs text-amber-400">
              Select a Notion connector credential to browse databases or enter the ID manually.
            </p>
          )}

          {form.source_type === "s3" && !form.connector_id && (
            <p className="text-xs text-amber-400">
              Select an S3 connector credential to authenticate.
            </p>
          )}

          <button
            onClick={create}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-lg text-sm font-medium transition shadow-lg shadow-emerald-500/15"
          >
            <Plus className="h-4 w-4" />
            Create Source
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-zinc-500 text-sm py-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading sources…
        </div>
      )}
      <div className="space-y-2">
        {sources.map((s) => {
          const conn = connectors.find((c) => c.id === s.connector_id);
          return (
            <div
              key={s.id}
              className="flex items-center justify-between bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 transition hover:border-zinc-700"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-zinc-950 border border-zinc-800">
                  <ServiceIcon type={s.source_type} size={22} />
                </div>
                <div>
                  <div className="font-medium text-zinc-200 flex items-center gap-2">
                    {s.name}
                    <SourceBadge type={s.source_type} />
                    <StatusBadge status={s.status} />
                  </div>
                  <div className="text-xs text-zinc-500">
                    {s.slug} · {s.chunk_count} chunks
                  </div>
                  {conn && (
                    <div className="text-xs text-zinc-600">Connector: {conn.name}</div>
                  )}
                  {s.source_type === "notion" && (
                    <div className="text-xs text-zinc-600">
                      {(() => {
                        const cfg = s.config as Record<string, string> | null;
                        if (cfg?.database_id) return `DB: ${cfg.database_id}`;
                        if (cfg?.page_id) return `Page: ${cfg.page_id}`;
                        return null;
                      })()}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => triggerSync(s.slug)}
                  disabled={syncingSlugs.has(s.slug)}
                  className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg transition"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${syncingSlugs.has(s.slug) ? "animate-spin" : ""}`} />
                  {syncingSlugs.has(s.slug) ? "Syncing…" : "Sync"}
                </button>
                <button
                  onClick={() => remove(s.slug)}
                  className="rounded-md p-2 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
        {!loading && sources.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
            <BookOpen className="h-10 w-10 text-zinc-700 mb-3" />
            <p className="text-sm">No knowledge sources configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
