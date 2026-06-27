import { useEffect, useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2, BookOpen, ChevronDown, ChevronRight, FileText, Clock, Layers, Pencil } from "lucide-react";
import {
  api,
  type Connector,
  type KnowledgeSource,
  type KnowledgeSourceCreate,
  type NotionResource,
  type S3Bucket,
  type GDriveResource,
  type SyncStatusOut,
} from "@/lib/api";
import ServiceIcon from "@/components/ServiceIcon";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-success-soft text-success border-success/20",
    syncing: "bg-warning-soft text-warning border-warning/20",
    pending: "bg-hover text-secondary border-line/60",
    error: "bg-danger-soft text-danger border-danger/20",
  };
  return (
    <span className={`text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border ${styles[status] || styles.pending}`}>
      {status}
    </span>
  );
}

function SourceBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    notion: "bg-brand/10 text-brand border-brand/20",
    s3: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    gdrive: "bg-green-500/10 text-green-400 border-green-500/20",
  };
  return (
    <span className={`text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border ${styles[type] || "bg-hover text-secondary border-line"}`}>
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

  // Google Drive browse state
  const [gdriveItems, setGdriveItems] = useState<GDriveResource[]>([]);
  const [gdriveBrowseLoading, setGdriveBrowseLoading] = useState(false);
  const [gdriveBrowseAttempted, setGdriveBrowseAttempted] = useState(false);
  const [gdriveFolderPath, setGdriveFolderPath] = useState<GDriveResource[]>([]);

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
    setGdriveItems([]);
    setGdriveBrowseAttempted(false);
    setGdriveFolderPath([]);
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
  const [expandedSync, setExpandedSync] = useState<string | null>(null);
  const [syncStatusData, setSyncStatusData] = useState<Record<string, SyncStatusOut>>({});
  const [syncStatusLoading, setSyncStatusLoading] = useState<string | null>(null);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [editName, setEditName] = useState("");

  const startEdit = (s: KnowledgeSource) => {
    setEditingSlug(s.slug);
    setEditName(s.name);
  };

  const saveEdit = async (slug: string) => {
    try {
      await api.updateKnowledgeSource(slug, { name: editName.trim() });
      setEditingSlug(null);
      refresh();
    } catch (e: any) {
      alert(`Update failed: ${e.message}`);
    }
  };

  const toggleSyncStatus = async (slug: string) => {
    if (expandedSync === slug) {
      setExpandedSync(null);
      return;
    }
    setExpandedSync(slug);
    if (!syncStatusData[slug]) {
      setSyncStatusLoading(slug);
      try {
        const data = await api.getSyncStatus(slug);
        setSyncStatusData((prev) => ({ ...prev, [slug]: data }));
      } catch (e: any) {
        alert(`Failed to load sync status: ${e.message}`);
      } finally {
        setSyncStatusLoading(null);
      }
    }
  };

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
          if (expandedSync === slug) {
            try {
              const data = await api.getSyncStatus(slug);
              setSyncStatusData((prev) => ({ ...prev, [slug]: data }));
            } catch (e: any) {
              console.error("Failed to refresh sync status:", e.message);
            }
          }
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

  const browseGdrive = async (folderId?: string) => {
    if (!form.connector_id) return;
    const conn = connectors.find((c) => c.id === form.connector_id);
    if (!conn) return;
    setGdriveBrowseLoading(true);
    setGdriveBrowseAttempted(true);
    try {
      const items = folderId
        ? await api.listGDriveChildren(conn.slug, folderId)
        : await api.listGDriveRoot(conn.slug);
      setGdriveItems(items);
    } catch (e: any) {
      alert(`Browse failed: ${e.message}`);
    } finally {
      setGdriveBrowseLoading(false);
    }
  };

  const selectGdriveFolder = (item: GDriveResource) => {
    if (item.type === "folder") {
      setGdriveFolderPath([...gdriveFolderPath, item]);
      browseGdrive(item.id);
    } else {
      // Selecting a file is not the use case; we sync folders
    }
  };

  const navigateGdriveTo = (index: number) => {
    if (index < 0) {
      setGdriveFolderPath([]);
      browseGdrive();
    } else {
      const target = gdriveFolderPath[index];
      setGdriveFolderPath(gdriveFolderPath.slice(0, index + 1));
      browseGdrive(target.id);
    }
  };

  const selectGdriveRoot = () => {
    const currentFolderId = gdriveFolderPath.length > 0 ? gdriveFolderPath[gdriveFolderPath.length - 1].id : "root";
    const currentFolderName = gdriveFolderPath.length > 0 ? gdriveFolderPath[gdriveFolderPath.length - 1].name : "Google Drive Root";
    setForm({
      ...form,
      name: form.name || currentFolderName,
      config: { ...form.config, folder_id: currentFolderId, folder_name: currentFolderName },
    });
  };

  const pickGdriveFolder = (item: GDriveResource) => {
    setForm({
      ...form,
      name: form.name || item.name,
      config: { ...form.config, folder_id: item.id, folder_name: item.name },
    });
  };

  const connectorOptions = connectors.filter((c) => {
    if (form.source_type === "notion") return c.connector_type === "notion";
    if (form.source_type === "s3") return c.connector_type === "s3";
    if (form.source_type === "gdrive") return c.connector_type === "gdrive";
    return true;
  });

  return (
    <div>
      <AdminPageHeader
        title="Knowledge Sources"
        description="Manage data sources for agent retrieval"
        icon={BookOpen}
        iconColor="text-warning"
        iconBg="bg-warning-soft"
      >
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-3.5 w-3.5" />
          {showForm ? "Cancel" : "Add Source"}
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
          <h2 className="font-medium text-primary">New Knowledge Source</h2>
          <input
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="Slug (e.g. notion-hr)"
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          />
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Name"
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
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
              setGdriveItems([]);
              setGdriveBrowseAttempted(false);
              setGdriveFolderPath([]);
            }}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          >
            <option value="notion">Notion</option>
            <option value="s3">S3 Bucket</option>
            <option value="gdrive">Google Drive</option>
          </select>

          {/* Connector selector */}
          <select
            value={form.connector_id || ""}
            onChange={(e) => {
              setForm({ ...form, connector_id: e.target.value || null });
              setS3Buckets([]);
              setS3BrowseAttempted(false);
              setGdriveItems([]);
              setGdriveBrowseAttempted(false);
              setGdriveFolderPath([]);
            }}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
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
                  className="bg-canvas border border-line rounded-lg px-2 py-1.5 text-sm text-primary focus:border-brand/50 outline-none transition"
                >
                  <option value="database">Browse Databases</option>
                  <option value="page">Browse Pages</option>
                </select>
                <button
                  onClick={browseNotion}
                  disabled={browseLoading}
                  className="text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white transition"
                >
                  {browseLoading ? "Browsing…" : "Browse Notion"}
                </button>
              </div>

              {browseItems.length > 0 && (
                <div className="border border-line rounded-lg p-2 space-y-1 max-h-40 overflow-y-auto bg-canvas">
                  <div className="text-xs text-tertiary mb-1">
                    Select a {browseMode === "database" ? "database" : "page"}:
                  </div>
                  {browseItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => selectItem(item)}
                      className={`w-full text-left px-2 py-1 rounded-md text-sm transition ${
                        selectedItem?.id === item.id
                          ? "bg-brand/10 text-brand border border-brand/20"
                          : "hover:bg-hover text-secondary"
                      }`}
                    >
                      {item.name}{" "}
                      <span className="text-xs text-tertiary">({item.id})</span>
                    </button>
                  ))}
                </div>
              )}

              {!browseLoading && browseAttempted && browseItems.length === 0 && (
                <p className="text-xs text-warning">
                  No {browseMode === "database" ? "databases" : "pages"} found. Make sure your Notion integration token is correct and the content is shared with the integration.
                </p>
              )}

              {selectedItem && (
                <div className="text-xs text-success">
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
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
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
                  className="text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white transition"
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
                  className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
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
                <p className="text-xs text-warning">
                  No buckets found. Check your S3 connector credentials.
                </p>
              )}

              <input
                value={(form.config?.bucket as string) || ""}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, bucket: e.target.value } })
                }
                placeholder="Or enter bucket name manually"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
              <input
                value={(form.config?.prefix as string) || ""}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, prefix: e.target.value } })
                }
                placeholder="Folder prefix (optional, e.g. docs/hr/)"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </div>
          )}

          {/* Google Drive folder browser */}
          {form.source_type === "gdrive" && form.connector_id && (
            <div className="space-y-2">
              <div className="flex gap-2 items-center">
                <button
                  onClick={() => browseGdrive()}
                  disabled={gdriveBrowseLoading}
                  className="text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white transition"
                >
                  {gdriveBrowseLoading ? "Loading…" : "Browse Drive"}
                </button>
              </div>

              {/* Breadcrumb navigation */}
              {gdriveFolderPath.length > 0 && (
                <div className="flex items-center gap-1 text-xs text-secondary flex-wrap">
                  <button onClick={() => navigateGdriveTo(-1)} className="hover:text-brand transition">
                    Root
                  </button>
                  {gdriveFolderPath.map((folder, i) => (
                    <span key={folder.id} className="flex items-center gap-1">
                      <span className="text-tertiary">/</span>
                      <button onClick={() => navigateGdriveTo(i)} className="hover:text-brand transition">
                        {folder.name}
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Folder/file listing */}
              {gdriveItems.length > 0 && (
                <div className="border border-line rounded-lg p-2 space-y-1 max-h-48 overflow-y-auto bg-canvas">
                  {gdriveItems.map((item) => {
                    const selected = (form.config?.folder_id as string) === item.id;
                    return (
                      <div
                        key={item.id}
                        className={`flex items-center justify-between px-2 py-1 rounded-md text-sm transition ${
                          selected ? "bg-success-soft border border-success/20" : ""
                        }`}
                      >
                        <button
                          onClick={() => item.type === "folder" ? selectGdriveFolder(item) : undefined}
                          className={`text-left flex-1 ${
                            item.type === "folder" ? "hover:text-brand text-primary" : "text-tertiary cursor-default"
                          }`}
                        >
                          {item.type === "folder" ? "📁" : "📄"} {item.name}
                        </button>
                        {item.type === "folder" && (
                          <button
                            onClick={() => pickGdriveFolder(item)}
                            className={`text-xs px-2 py-0.5 rounded transition ${
                              selected
                                ? "bg-success/20 text-success"
                                : "bg-hover hover:bg-hover text-secondary"
                            }`}
                          >
                            {selected ? "✓ Selected" : "Select"}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {!gdriveBrowseLoading && gdriveBrowseAttempted && gdriveItems.length === 0 && (
                <p className="text-xs text-warning">
                  No items found. Check your Google Drive connector credentials and permissions.
                </p>
              )}

              {/* Select current folder button */}
              {gdriveBrowseAttempted && (
                <button
                  onClick={selectGdriveRoot}
                  className="text-sm bg-success/80 hover:bg-success-hover px-3 py-1.5 rounded-lg text-white transition"
                >
                  Use this folder
                </button>
              )}

              <input
                value={(form.config?.folder_id as string) || ""}
                onChange={(e) =>
                  setForm({ ...form, config: { ...form.config, folder_id: e.target.value } })
                }
                placeholder="Or enter folder ID manually"
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </div>
          )}

          {form.source_type === "notion" && !form.connector_id && (
            <p className="text-xs text-warning">
              Select a Notion connector credential to browse databases or enter the ID manually.
            </p>
          )}

          {form.source_type === "s3" && !form.connector_id && (
            <p className="text-xs text-warning">
              Select an S3 connector credential to authenticate.
            </p>
          )}

          {form.source_type === "gdrive" && !form.connector_id && (
            <p className="text-xs text-warning">
              Select a Google Drive connector credential to browse folders.
            </p>
          )}

          <button
            onClick={create}
            className="flex items-center gap-1.5 bg-success hover:bg-success-hover px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-success/15"
          >
            <Plus className="h-4 w-4" />
            Create Source
          </button>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-tertiary text-sm py-2">
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
              className="bg-card border border-line rounded-xl transition hover:border-line overflow-hidden"
            >
              <div className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-canvas border border-line">
                    <ServiceIcon type={s.source_type} size={22} />
                  </div>
                  <div className="flex-1">
                    {editingSlug === s.slug ? (
                      <div className="flex items-center gap-2">
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") saveEdit(s.slug);
                            if (e.key === "Escape") setEditingSlug(null);
                          }}
                          autoFocus
                          className="bg-canvas border border-brand/50 rounded-lg px-2 py-1 text-sm text-primary outline-none focus:ring-2 focus:ring-brand/10"
                        />
                        <button
                          onClick={() => saveEdit(s.slug)}
                          className="text-xs bg-success hover:bg-success-hover px-2 py-1 rounded-md text-white transition"
                        >Save</button>
                        <button
                          onClick={() => setEditingSlug(null)}
                          className="text-xs text-tertiary hover:text-secondary px-2 py-1 transition"
                        >Cancel</button>
                      </div>
                    ) : (
                      <div className="font-medium text-primary flex items-center gap-2">
                        {s.name}
                        <SourceBadge type={s.source_type} />
                        <StatusBadge status={s.status} />
                      </div>
                    )}
                    <div className="text-xs text-tertiary">
                      {s.slug} · {s.chunk_count} chunks
                      {s.last_sync_at && (
                        <span className="ml-2">· Last sync: {new Date(s.last_sync_at).toLocaleString()}</span>
                      )}
                    </div>
                    {conn && (
                      <div className="text-xs text-tertiary">Connector: {conn.name}</div>
                    )}
                    {s.source_type === "notion" && (
                      <div className="text-xs text-tertiary">
                        {(() => {
                          const cfg = s.config as Record<string, string> | null;
                          if (cfg?.database_id) return `Database: ${cfg.database_id.slice(0, 8)}…`;
                          if (cfg?.page_id) return `Page: ${cfg.page_id.slice(0, 8)}…`;
                          return null;
                        })()}
                      </div>
                    )}
                    {s.source_type === "gdrive" && (
                      <div className="text-xs text-tertiary">
                        {(() => {
                          const cfg = s.config as Record<string, string> | null;
                          if (cfg?.folder_name) return `Folder: ${cfg.folder_name}`;
                          if (cfg?.folder_id) return `Folder: ${cfg.folder_id.slice(0, 8)}…`;
                          return null;
                        })()}
                      </div>
                    )}
                    {s.source_type === "s3" && (
                      <div className="text-xs text-tertiary">
                        {(() => {
                          const cfg = s.config as Record<string, string> | null;
                          if (cfg?.bucket) return `s3://${cfg.bucket}/${cfg.prefix || ""}`;
                          return null;
                        })()}
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {editingSlug !== s.slug && (
                    <button
                      onClick={() => startEdit(s)}
                      className="rounded-md p-2 text-tertiary hover:text-brand hover:bg-brand/10 transition"
                      title="Rename"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    onClick={() => toggleSyncStatus(s.slug)}
                    className="flex items-center gap-1 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-1.5 rounded-lg transition"
                  >
                    {expandedSync === s.slug ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    Details
                  </button>
                  <button
                    onClick={() => triggerSync(s.slug)}
                    disabled={syncingSlugs.has(s.slug)}
                    className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg text-white transition"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${syncingSlugs.has(s.slug) ? "animate-spin" : ""}`} />
                    {syncingSlugs.has(s.slug) ? "Syncing…" : "Sync"}
                  </button>
                  <button
                    onClick={() => remove(s.slug)}
                    className="rounded-md p-2 text-tertiary hover:text-danger hover:bg-danger-soft transition"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {expandedSync === s.slug && (
                <div className="border-t border-line/60 bg-canvas/50 px-4 py-3">
                  {syncStatusLoading === s.slug ? (
                    <div className="flex items-center gap-2 text-tertiary text-sm py-4">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading sync status…
                    </div>
                  ) : syncStatusData[s.slug] ? (
                    (() => {
                      const status = syncStatusData[s.slug];
                      const cleanTitle = (title: string) => {
                        const parts = title.split(" - ");
                        return parts.length > 1 ? parts.slice(1).join(" - ") : title;
                      };
                      return (
                        <div className="space-y-3">
                          <div className="flex items-center gap-4 text-xs">
                            <span className="flex items-center gap-1.5 text-secondary">
                              <Layers className="h-3.5 w-3.5 text-tertiary" />
                              <span className="font-medium text-primary">{status.document_count}</span> docs
                            </span>
                            <span className="flex items-center gap-1.5 text-secondary">
                              <FileText className="h-3.5 w-3.5 text-tertiary" />
                              <span className="font-medium text-primary">{status.chunk_count}</span> chunks
                            </span>
                            {status.last_sync_at && (
                              <span className="flex items-center gap-1.5 text-secondary">
                                <Clock className="h-3.5 w-3.5 text-tertiary" />
                                {new Date(status.last_sync_at).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                              </span>
                            )}
                            <StatusBadge status={status.status} />
                          </div>

                          {status.documents.length > 0 ? (
                            <div className="border border-line/60 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
                              <table className="w-full text-xs">
                                <thead className="sticky top-0">
                                  <tr className="bg-hover text-tertiary">
                                    <th className="text-left font-medium px-3 py-2">Document</th>
                                    <th className="text-right font-medium px-3 py-2 w-16">Chunks</th>
                                    <th className="text-left font-medium px-3 py-2 w-36">Modified</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {status.documents.map((doc) => (
                                    <tr key={doc.source_id} className="border-t border-line/40 hover:bg-hover/50">
                                      <td className="px-3 py-2 text-secondary">
                                        <div className="flex items-center gap-2">
                                          <FileText className="h-3 w-3 shrink-0 text-tertiary" />
                                          <span className="truncate max-w-[280px]" title={doc.title}>{cleanTitle(doc.title)}</span>
                                        </div>
                                      </td>
                                      <td className="px-3 py-2 text-right text-tertiary tabular-nums">{doc.chunk_count}</td>
                                      <td className="px-3 py-2 text-tertiary whitespace-nowrap">
                                        {doc.source_modified_at
                                          ? new Date(doc.source_modified_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
                                          : "—"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="flex flex-col items-center justify-center py-6 text-tertiary">
                              <FileText className="h-6 w-6 mb-2 opacity-50" />
                              <p className="text-xs">No documents ingested yet. Run a sync to populate this source.</p>
                            </div>
                          )}

                          <button
                            onClick={() => {
                              setSyncStatusLoading(s.slug);
                              api.getSyncStatus(s.slug).then((data) => {
                                setSyncStatusData((prev) => ({ ...prev, [s.slug]: data }));
                                setSyncStatusLoading(null);
                              });
                            }}
                            className="flex items-center gap-1.5 text-xs text-tertiary hover:text-secondary transition"
                          >
                            <RefreshCw className="h-3 w-3" />
                            Refresh status
                          </button>
                        </div>
                      );
                    })()
                  ) : (
                    <p className="text-xs text-tertiary py-2">Failed to load sync status.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {!loading && sources.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-tertiary">
            <BookOpen className="h-10 w-10 text-tertiary mb-3" />
            <p className="text-sm">No knowledge sources configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
