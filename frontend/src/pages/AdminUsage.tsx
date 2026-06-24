import { useEffect, useState, useCallback } from "react";
import { BarChart3, Coins, Cpu, Trash2, Plus, RefreshCw, AlertTriangle } from "lucide-react";
import { api, type Agent, type UsageSummary, type UsageTimeseriesPoint, type RecentUsageItem, type TokenBudgetOut, type TokenBudgetCreate } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

type BreakdownTab = "agent" | "user" | "model";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(n: number): string {
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n >= 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(6)}`;
}

function formatDate(s: string): string {
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function SummaryCard({ icon: Icon, label, value, sub }: { icon: typeof BarChart3; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line/60 bg-card p-5">
      <div className="flex items-center gap-2 text-tertiary mb-2">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-2xl font-semibold text-primary">{value}</p>
      {sub && <p className="text-xs text-tertiary mt-1">{sub}</p>}
    </div>
  );
}

function MiniBarChart({ data, metric }: { data: UsageTimeseriesPoint[]; metric: "tokens" | "cost" }) {
  const values = data.map((d) =>
    metric === "tokens" ? Number(d.total_tokens) : Number(d.total_cost_usd)
  );
  const maxVal = values.length > 0 ? Math.max(...values) : 1;
  const gridCount = 5;

  function fmtVal(v: number): string {
    return metric === "tokens" ? formatTokens(v) : formatCost(v);
  }

  function fmtDate(s: string): string {
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  return (
    <div className="flex h-52 w-full">
      {/* Y-axis labels */}
      <div className="flex flex-col justify-between pr-3 text-right w-16 shrink-0">
        {Array.from({ length: gridCount + 1 }).map((_, i) => {
          const val = maxVal * (1 - i / gridCount);
          return (
            <span key={i} className="text-[10px] text-tertiary leading-none">
              {fmtVal(val)}
            </span>
          );
        })}
      </div>

      {/* Chart area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Grid + bars */}
        <div className="relative flex-1">
          {/* Horizontal gridlines */}
          {Array.from({ length: gridCount + 1 }).map((_, i) => (
            <div
              key={i}
              className="absolute left-0 right-0 border-t border-line/60"
              style={{ top: `${(i / gridCount) * 100}%` }}
            />
          ))}

          {/* Bars */}
          <div className="absolute inset-0 flex items-end justify-around gap-1 px-2">
            {data.map((d, i) => {
              const val = metric === "tokens" ? Number(d.total_tokens) : Number(d.total_cost_usd);
              const pct = maxVal > 0 ? (val / maxVal) * 100 : 0;
              const dateLabel = fmtDate(d.date);
              return (
                <div key={i} className="h-full flex flex-col items-center justify-end flex-1 min-w-0">
                  <div
                    className="w-full max-w-[24px] bg-brand/80 rounded-t-sm hover:bg-brand-hover transition-all relative group"
                    style={{ height: `${Math.max(pct, 3)}%` }}
                  >
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 hidden group-hover:block bg-hover text-xs text-primary px-2 py-1 rounded whitespace-nowrap z-10 border border-line">
                      {dateLabel}: {fmtVal(val)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* X-axis labels */}
        <div className="flex justify-around gap-1 px-2 pt-2 border-t border-line/60 mt-1">
          {data.map((d, i) => (
            <div key={i} className="flex-1 min-w-0 text-center">
              <span className="text-[10px] text-tertiary truncate block">{fmtDate(d.date)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BreakdownTable({ tab, summary }: { tab: BreakdownTab; summary: UsageSummary }) {
  const rows =
    tab === "agent"
      ? summary.by_agent.map((r) => ({ id: r.agent_slug, label: r.agent_slug, tokens: r.tokens, cost: r.cost, requests: r.requests }))
      : tab === "user"
      ? summary.by_user.map((r) => ({ id: r.user_id, label: r.user_email || r.user_id.slice(0, 8), tokens: r.tokens, cost: r.cost, requests: r.requests }))
      : summary.by_model.map((r) => ({ id: r.model, label: r.model, tokens: r.tokens, cost: r.cost, requests: r.requests }));

  if (rows.length === 0) {
    return <p className="text-sm text-tertiary py-8 text-center">No data for this period.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-tertiary border-b border-line/60">
            <th className="pb-2 pr-4 font-medium">{tab === "agent" ? "Agent" : tab === "user" ? "User" : "Model"}</th>
            <th className="pb-2 pr-4 font-medium text-right">Tokens</th>
            <th className="pb-2 pr-4 font-medium text-right">Cost</th>
            <th className="pb-2 pr-4 font-medium text-right">Requests</th>
            <th className="pb-2 font-medium text-right">Avg Tokens/Req</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line/60 hover:bg-hover">
              <td className="py-2 pr-4 text-primary font-medium">{r.label}</td>
              <td className="py-2 pr-4 text-right text-secondary">{formatTokens(r.tokens)}</td>
              <td className="py-2 pr-4 text-right text-secondary">{formatCost(r.cost)}</td>
              <td className="py-2 pr-4 text-right text-secondary">{r.requests}</td>
              <td className="py-2 text-right text-secondary">{r.requests > 0 ? formatTokens(Math.round(r.tokens / r.requests)) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminUsage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [timeseries, setTimeseries] = useState<UsageTimeseriesPoint[]>([]);
  const [recent, setRecent] = useState<RecentUsageItem[]>([]);
  const [budgets, setBudgets] = useState<TokenBudgetOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartMetric, setChartMetric] = useState<"tokens" | "cost">("tokens");
  const [breakdownTab, setBreakdownTab] = useState<BreakdownTab>("agent");
  const [chartDays, setChartDays] = useState(30);
  const [showBudgetForm, setShowBudgetForm] = useState(false);
  const [newBudget, setNewBudget] = useState<TokenBudgetCreate>({ scope: "user", scope_id: "*", monthly_cost_limit_usd: 50.0 });
  const [availableAgents, setAvailableAgents] = useState<Agent[]>([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, ts, r, b, agentsList] = await Promise.all([
        api.getUsageSummary(),
        api.getUsageTimeseries({ days: chartDays }),
        api.getRecentUsage({ limit: 50 }),
        api.getBudgets(),
        api.listAgents(),
      ]);
      setSummary(s);
      setTimeseries(ts);
      setRecent(r);
      setBudgets(b);
      setAvailableAgents(agentsList);
    } catch (e: any) {
      setError(e.message || "Failed to load usage data");
    } finally {
      setLoading(false);
    }
  }, [chartDays]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleSaveBudget = async () => {
    try {
      await api.upsertBudget(newBudget);
      setShowBudgetForm(false);
      setNewBudget({ scope: "user", scope_id: "*", monthly_cost_limit_usd: 50.0 });
      const b = await api.getBudgets();
      setBudgets(b);
    } catch (e: any) {
      setError(e.message || "Failed to save budget");
    }
  };

  const handleDeleteBudget = async (id: string) => {
    try {
      await api.deleteBudget(id);
      setBudgets(budgets.filter((b) => b.id !== id));
    } catch (e: any) {
      setError(e.message || "Failed to delete budget");
    }
  };

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="h-5 w-5 animate-spin text-tertiary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Usage"
        description="Track consumption and manage budgets"
      >
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-sm text-secondary hover:bg-hover/70 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard icon={BarChart3} label="Total Tokens" value={formatTokens(summary.total_tokens)} sub={`${formatTokens(summary.input_tokens)} in / ${formatTokens(summary.output_tokens)} out`} />
          <SummaryCard icon={Coins} label="Est. Cost" value={formatCost(summary.total_cost_usd)} sub="This month" />
          <SummaryCard icon={Cpu} label="Requests" value={String(summary.total_requests)} sub="LLM calls" />
          <SummaryCard icon={BarChart3} label="Active Agents" value={String(summary.by_agent.length)} sub={`${summary.by_user.length} users`} />
        </div>
      )}

      {/* Chart */}
      <div className="rounded-xl border border-line/60 bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-primary">Daily Usage</h3>
          <div className="flex items-center gap-2">
            <select
              value={chartDays}
              onChange={(e) => setChartDays(Number(e.target.value))}
              className="rounded-lg border border-line bg-card px-2 py-1 text-xs text-secondary"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
            </select>
            <div className="flex rounded-lg border border-line overflow-hidden">
              <button
                onClick={() => setChartMetric("tokens")}
                className={`px-3 py-1 text-xs transition ${chartMetric === "tokens" ? "bg-brand text-white" : "bg-hover text-secondary hover:text-primary"}`}
              >
                Tokens
              </button>
              <button
                onClick={() => setChartMetric("cost")}
                className={`px-3 py-1 text-xs transition ${chartMetric === "cost" ? "bg-brand text-white" : "bg-hover text-secondary hover:text-primary"}`}
              >
                Cost
              </button>
            </div>
          </div>
        </div>
        {timeseries.length > 0 ? (
          <MiniBarChart data={timeseries} metric={chartMetric} />
        ) : (
          <p className="text-sm text-tertiary py-10 text-center">No usage data for the selected period.</p>
        )}
      </div>

      {/* Breakdown tabs */}
      {summary && (
        <div className="rounded-xl border border-line/60 bg-card p-5">
          <div className="flex items-center gap-2 mb-4">
            {(["agent", "user", "model"] as BreakdownTab[]).map((t) => (
              <button
                key={t}
                onClick={() => setBreakdownTab(t)}
                className={`rounded-lg px-3 py-1.5 text-sm transition capitalize ${breakdownTab === t ? "bg-hover text-primary" : "text-secondary hover:text-primary"}`}
              >
                By {t}
              </button>
            ))}
          </div>
          <BreakdownTable tab={breakdownTab} summary={summary} />
        </div>
      )}

      {/* Budgets */}
      <div className="rounded-xl border border-line/60 bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-primary">Budgets</h3>
          <button
            onClick={() => setShowBudgetForm(!showBudgetForm)}
            className="flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-xs text-white hover:bg-brand-hover transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Budget
          </button>
        </div>

        {showBudgetForm && (
          <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-line/60 bg-canvas p-4">
            <div>
              <label className="block text-xs text-tertiary mb-1">Scope</label>
              <select
                value={newBudget.scope}
                onChange={(e) => {
                  const scope = e.target.value;
                  setNewBudget({ scope, scope_id: scope === "user" ? "*" : (availableAgents[0]?.slug || ""), monthly_cost_limit_usd: 50.0 });
                }}
                className="rounded-lg border border-line bg-card px-3 py-1.5 text-sm text-primary"
              >
                <option value="user">All Users</option>
                <option value="agent">Agent</option>
              </select>
            </div>
            {newBudget.scope === "user" ? (
              <div className="flex items-center text-sm text-secondary py-1.5">
                Global limit applies to all users
              </div>
            ) : (
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs text-tertiary mb-1">Agent</label>
                <select
                  value={newBudget.scope_id}
                  onChange={(e) => setNewBudget({ ...newBudget, scope_id: e.target.value })}
                  className="w-full rounded-lg border border-line bg-card px-3 py-1.5 text-sm text-primary"
                >
                  {availableAgents.map((a) => (
                    <option key={a.slug} value={a.slug}>{a.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="block text-xs text-tertiary mb-1">Monthly Cost Limit (USD)</label>
              <input
                type="number"
                step="0.01"
                value={newBudget.monthly_cost_limit_usd}
                onChange={(e) => setNewBudget({ ...newBudget, monthly_cost_limit_usd: Number(e.target.value) })}
                className="w-40 rounded-lg border border-line bg-card px-3 py-1.5 text-sm text-primary"
              />
            </div>
            <button
              onClick={handleSaveBudget}
              className="rounded-lg bg-success px-4 py-1.5 text-sm text-white hover:bg-success-hover transition"
            >
              Save
            </button>
          </div>
        )}

        {budgets.length === 0 ? (
          <p className="text-sm text-tertiary py-4 text-center">No budgets configured.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-tertiary border-b border-line/60">
                <th className="pb-2 pr-4 font-medium">Scope</th>
                <th className="pb-2 pr-4 font-medium">ID</th>
                <th className="pb-2 pr-4 font-medium text-right">Monthly Limit</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {budgets.map((b) => (
                <tr key={b.id} className="border-b border-line/60 hover:bg-hover">
                  <td className="py-2 pr-4">
                    <span className={`rounded px-2 py-0.5 text-xs ${b.scope === "user" ? "bg-brand/10 text-brand border border-brand/20" : "bg-violet-500/10 text-violet-400 border border-violet-500/20"}`}>
                      {b.scope}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-secondary text-xs">{b.scope === "user" ? "All users" : b.scope_id}</td>
                  <td className="py-2 pr-4 text-right text-secondary">${b.monthly_cost_limit_usd.toFixed(2)}</td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => handleDeleteBudget(b.id)}
                      className="text-tertiary hover:text-danger transition"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent requests */}
      <div className="rounded-xl border border-line/60 bg-card p-5">
        <h3 className="text-sm font-semibold text-primary mb-4">Recent Requests</h3>
        {recent.length === 0 ? (
          <p className="text-sm text-tertiary py-4 text-center">No recent usage records.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-tertiary border-b border-line/60">
                  <th className="pb-2 pr-4 font-medium">Time</th>
                  <th className="pb-2 pr-4 font-medium">User</th>
                  <th className="pb-2 pr-4 font-medium">Agent</th>
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium text-right">In</th>
                  <th className="pb-2 pr-4 font-medium text-right">Out</th>
                  <th className="pb-2 pr-4 font-medium text-right">Total</th>
                  <th className="pb-2 font-medium text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r) => (
                  <tr key={r.id} className="border-b border-line/60 hover:bg-hover">
                    <td className="py-2 pr-4 text-secondary text-xs">{formatDate(r.created_at)}</td>
                    <td className="py-2 pr-4 text-secondary text-xs">{r.user_email || "—"}</td>
                    <td className="py-2 pr-4 text-secondary">{r.agent_slug}</td>
                    <td className="py-2 pr-4 text-secondary text-xs font-mono">{r.model}</td>
                    <td className="py-2 pr-4 text-right text-secondary">{formatTokens(r.input_tokens)}</td>
                    <td className="py-2 pr-4 text-right text-secondary">{formatTokens(r.output_tokens)}</td>
                    <td className="py-2 pr-4 text-right text-primary font-medium">{formatTokens(r.total_tokens)}</td>
                    <td className="py-2 text-right text-secondary">{formatCost(r.estimated_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
