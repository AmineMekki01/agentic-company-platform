import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Database,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Layers,
  Plug,
} from "lucide-react";
import { api, type SystemStatus } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

const KS_STATUS_BADGE: Record<string, string> = {
  ready: "bg-success-soft text-success border-success/20",
  syncing: "bg-brand/10 text-brand border-brand/20",
  pending: "bg-hover text-tertiary border-line",
  error: "bg-danger-soft text-danger border-danger/20",
};

function ServiceCard({
  name,
  icon: Icon,
  health,
}: {
  name: string;
  icon: typeof Database;
  health: { status: string; detail?: string; collections?: number };
}) {
  const ok = health.status === "ok";
  return (
    <div className="rounded-2xl border border-line/60 bg-card p-5 shadow-sm backdrop-blur-sm transition hover:border-line">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-hover ring-1 ring-line/60">
            <Icon className="h-5 w-5 text-secondary" />
          </div>
          <div>
            <p className="text-sm font-medium text-primary capitalize">{name}</p>
            {health.collections !== undefined && (
              <p className="text-[11px] text-tertiary">{health.collections} collections</p>
            )}
          </div>
        </div>
        {ok ? (
          <CheckCircle2 className="h-5 w-5 text-success" />
        ) : (
          <XCircle className="h-5 w-5 text-danger" />
        )}
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`text-xs font-semibold uppercase tracking-wide ${
            ok ? "text-success" : "text-danger"
          }`}
        >
          {ok ? "Operational" : "Down"}
        </span>
        {!ok && health.detail && (
          <span className="text-[11px] text-tertiary truncate" title={health.detail}>
            — {health.detail}
          </span>
        )}
      </div>
    </div>
  );
}

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

export default function AdminHealth() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api.getSystemStatus();
      setStatus(data);
      setError("");
      setLastUpdated(new Date());
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Failed to fetch status";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(refresh, 300000); // 5 minutes, we can change this and addapt, for the moment i will use 5 min
    return () => clearInterval(interval);
  }, [autoRefresh, refresh]);

  const overallOk = status?.status === "ok";

  return (
    <div>
      <AdminPageHeader
        title="System Status"
        description="Real-time health of infrastructure services and data connectors"
        icon={Activity}
        iconColor="text-brand"
        iconBg="bg-brand/10"
      >
        <button
          onClick={() => setAutoRefresh((s) => !s)}
          className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg border transition ${
            autoRefresh
              ? "bg-brand/10 border-brand/20 text-brand"
              : "bg-card border-line/60 text-secondary hover:bg-hover"
          }`}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} />
          {autoRefresh ? "Live" : "Paused"}
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
        <div className="mb-6 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}

      {loading && !status ? (
        <div className="flex items-center justify-center py-20 text-secondary">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          Loading status…
        </div>
      ) : status ? (
        <>
          {/* Overall banner */}
          <div
            className={`mb-6 flex items-center gap-3 rounded-2xl border px-5 py-4 ${
              overallOk
                ? "border-success/20 bg-success-soft"
                : "border-warning/20 bg-warning-soft"
            }`}
          >
            {overallOk ? (
              <CheckCircle2 className="h-6 w-6 text-success" />
            ) : (
              <AlertTriangle className="h-6 w-6 text-warning" />
            )}
            <div className="flex-1">
              <p
                className={`text-sm font-semibold ${
                  overallOk ? "text-success" : "text-warning"
                }`}
              >
                {overallOk ? "All systems operational" : "Some services are degraded"}
              </p>
              <p className="text-xs text-tertiary">
                {status.service} · {status.environment}
                {lastUpdated && ` · Updated ${timeAgo(lastUpdated.toISOString())}`}
              </p>
            </div>
          </div>

          {/* Service cards */}
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-tertiary">
            Infrastructure Services
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-8">
            <ServiceCard name="PostgreSQL" icon={Database} health={status.services.database} />
            <ServiceCard name="Qdrant" icon={Layers} health={status.services.qdrant} />
            <ServiceCard name="Redis" icon={Activity} health={status.services.redis} />
          </div>

          {/* Knowledge Sources */}
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-tertiary">
            Knowledge Sources
          </h2>
          {status.knowledge_sources.length === 0 ? (
            <div className="rounded-2xl border border-line/60 bg-card p-8 text-center text-sm text-tertiary mb-8">
              No knowledge sources configured
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-line/60 bg-card mb-8">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line/60 bg-hover/50">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-tertiary">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-tertiary">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-tertiary">Status</th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-tertiary">Chunks</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-tertiary">Connector</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-tertiary">Last Sync</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/40">
                  {status.knowledge_sources.map((ks) => (
                    <tr key={ks.id} className="hover:bg-hover/30 transition">
                      <td className="px-4 py-3">
                        <p className="font-medium text-primary">{ks.name}</p>
                        <p className="text-[11px] text-tertiary">{ks.slug}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-secondary capitalize">{ks.source_type}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-[10px] uppercase font-semibold tracking-wide rounded-md px-2 py-0.5 border ${
                            KS_STATUS_BADGE[ks.status] || KS_STATUS_BADGE.pending
                          }`}
                        >
                          {ks.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-secondary tabular-nums">
                        {ks.chunk_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-secondary">
                        {ks.connector_name || <span className="text-tertiary">—</span>}
                      </td>
                      <td className="px-4 py-3 text-tertiary">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {timeAgo(ks.last_sync_at)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Connectors */}
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-tertiary">
            Connectors
          </h2>
          {status.connectors.length === 0 ? (
            <div className="rounded-2xl border border-line/60 bg-card p-8 text-center text-sm text-tertiary">
              No connectors configured
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {status.connectors.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-3 rounded-xl border border-line/60 bg-card p-4 shadow-sm"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-hover ring-1 ring-line/60">
                    <Plug className="h-4 w-4 text-secondary" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-primary">{c.name}</p>
                    <p className="text-[11px] text-tertiary">
                      {c.connector_type} · {c.slug}
                    </p>
                  </div>
                  <CheckCircle2 className="h-4 w-4 text-success shrink-0" />
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
