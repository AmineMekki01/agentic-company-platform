import { useEffect, useState } from "react";
import { Cpu, Save, Loader2, Plug, CheckCircle2, XCircle, Cloud, HardDrive } from "lucide-react";
import { api, type LLMSettings, type OllamaModelInfo, type OllamaTestResult } from "@/lib/api";
import AdminPageHeader from "@/components/admin/AdminPageHeader";

export default function AdminLLMModels() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<OllamaTestResult | null>(null);
  const [discoveredModels, setDiscoveredModels] = useState<OllamaModelInfo[]>([]);
  const [urlInput, setUrlInput] = useState("");

  useEffect(() => {
    api.getLLMSettings()
      .then((s) => {
        setSettings(s);
        setUrlInput(s.ollama_base_url);
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load LLM settings");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-secondary">
        <Cpu className="mr-2 h-4 w-4 animate-spin" />
        Loading…
      </div>
    );
  }

  if (!settings) {
    return <div className="text-danger">{error || "Unable to load settings"}</div>;
  }

  async function handleTestConnection() {
    setTesting(true);
    setTestResult(null);
    setDiscoveredModels([]);
    setError("");
    try {
      const result = await api.testOllamaConnection(urlInput);
      setTestResult(result);
      if (result.connected) {
        setDiscoveredModels(result.models);
      }
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Test failed";
      setTestResult({ connected: false, models: [], error: detail });
    } finally {
      setTesting(false);
    }
  }

  function toggleModel(modelName: string) {
    const fullName = modelName.startsWith("ollama/") ? modelName : `ollama/${modelName}`;
    setSettings((s) => {
      if (!s) return s;
      const has = s.ollama_enabled_models.includes(fullName);
      return {
        ...s,
        ollama_enabled_models: has
          ? s.ollama_enabled_models.filter((m) => m !== fullName)
          : [...s.ollama_enabled_models, fullName],
      };
    });
  }

  function addDiscoveredModel(model: OllamaModelInfo) {
    const fullName = `ollama/${model.name}`;
    setSettings((s) => {
      if (!s) return s;
      if (s.ollama_enabled_models.includes(fullName)) return s;
      return { ...s, ollama_enabled_models: [...s.ollama_enabled_models, fullName] };
    });
  }

  function addAllDiscovered() {
    setSettings((s) => {
      if (!s) return s;
      const existing = new Set(s.ollama_enabled_models);
      const toAdd = discoveredModels
        .map((m) => `ollama/${m.name}`)
        .filter((name) => !existing.has(name));
      return { ...s, ollama_enabled_models: [...s.ollama_enabled_models, ...toAdd] };
    });
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api.updateLLMSettings({
        ollama_enabled: settings.ollama_enabled,
        ollama_base_url: urlInput,
        ollama_enabled_models: settings.ollama_enabled_models,
      });
      setSettings(updated);
      setSuccess("Settings saved successfully");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Save failed";
      setError(detail);
    } finally {
      setSaving(false);
    }
  }

  const enabledSet = new Set(settings.ollama_enabled_models);

  return (
    <div className="mx-auto max-w-3xl">
      <AdminPageHeader
        title="LLM Models"
        description="Configure cloud and local LLM providers available to your agents"
        icon={Cpu}
        iconColor="text-brand"
        iconBg="bg-brand/10"
      />

      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success-soft px-4 py-3 text-sm text-success">
          {success}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* Cloud (API) section */}
        <div className="rounded-2xl border border-line/60 bg-card p-5 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand/10">
              <Cloud className="h-4 w-4 text-brand" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-primary">Cloud (API)</h2>
              <p className="text-xs text-tertiary">OpenAI models — always available</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {["gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.4", "gpt-5.5"].map((m) => (
              <span
                key={m}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line/60 bg-canvas px-3 py-1.5 text-xs font-medium text-secondary"
              >
                <CheckCircle2 className="h-3 w-3 text-success" />
                {m}
              </span>
            ))}
          </div>
        </div>

        {/* Local (Ollama) section */}
        <div className="rounded-2xl border border-line/60 bg-card p-5 space-y-5 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10">
                <HardDrive className="h-4 w-4 text-violet-500" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-primary">Local (Ollama)</h2>
                <p className="text-xs text-tertiary">Run models on your own hardware via Ollama</p>
              </div>
            </div>
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={settings.ollama_enabled}
                onChange={(e) =>
                  setSettings((s) => (s ? { ...s, ollama_enabled: e.target.checked } : s))
                }
                className="h-4 w-4 rounded border-line bg-hover text-brand focus:ring-brand"
              />
              <span className="text-sm font-medium text-primary">Enabled</span>
            </label>
          </div>

          {/* Ollama URL */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-secondary">
              Ollama Server URL
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                placeholder="http://ollama:11434/v1"
                className="flex-1 rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-primary outline-none transition focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testing || !urlInput}
                className="inline-flex items-center gap-1.5 rounded-xl border border-line/60 bg-canvas px-3 py-2 text-sm text-secondary transition hover:bg-hover disabled:opacity-50"
              >
                {testing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plug className="h-4 w-4" />
                )}
                {testing ? "Testing…" : "Test & Fetch"}
              </button>
            </div>
            <p className="mt-1 text-[11px] text-tertiary">
              The OpenAI-compatible endpoint (usually <code className="text-secondary">:11434/v1</code>).
              Click "Test & Fetch" to discover installed models.
            </p>
          </div>

          {/* Test result */}
          {testResult && (
            <div
              className={`rounded-xl border p-3 text-sm ${
                testResult.connected
                  ? "border-success/30 bg-success-soft text-success"
                  : "border-danger/30 bg-danger-soft text-danger"
              }`}
            >
              <div className="flex items-center gap-2">
                {testResult.connected ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                ) : (
                  <XCircle className="h-4 w-4 shrink-0" />
                )}
                <span>
                  {testResult.connected
                    ? `Connected — ${testResult.models.length} model${testResult.models.length !== 1 ? "s" : ""} found`
                    : `Connection failed: ${testResult.error}`}
                </span>
              </div>
            </div>
          )}

          {/* Discovered models */}
          {discoveredModels.length > 0 && (
            <div className="rounded-xl border border-line/60 bg-canvas p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-secondary">
                  Discovered Models ({discoveredModels.length})
                </span>
                <button
                  type="button"
                  onClick={addAllDiscovered}
                  className="text-xs font-medium text-brand hover:text-brand-hover transition"
                >
                  + Add all
                </button>
              </div>
              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {discoveredModels.map((model) => {
                  const fullName = `ollama/${model.name}`;
                  const isEnabled = enabledSet.has(fullName);
                  return (
                    <div
                      key={model.name}
                      className="flex items-center justify-between rounded-lg border border-line/40 bg-card px-3 py-2"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm text-primary truncate">{model.name}</span>
                        {model.size && (
                          <span className="text-[11px] text-tertiary shrink-0">{model.size}</span>
                        )}
                        {model.quantization && (
                          <span className="text-[11px] text-tertiary shrink-0">{model.quantization}</span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => (isEnabled ? toggleModel(model.name) : addDiscoveredModel(model))}
                        className={`text-xs font-medium px-2 py-1 rounded-lg transition shrink-0 ${
                          isEnabled
                            ? "text-danger hover:bg-danger-soft"
                            : "text-brand hover:bg-brand/10"
                        }`}
                      >
                        {isEnabled ? "Remove" : "+ Add"}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Enabled models list */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-secondary">
                Enabled Models ({settings.ollama_enabled_models.length})
              </span>
              {settings.ollama_enabled_models.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    setSettings((s) => (s ? { ...s, ollama_enabled_models: [] } : s))
                  }
                  className="text-xs text-danger hover:underline"
                >
                  Clear all
                </button>
              )}
            </div>
            {settings.ollama_enabled_models.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line/60 bg-canvas px-4 py-6 text-center">
                <p className="text-sm text-tertiary">
                  No local models enabled. Test your Ollama connection and add models above.
                </p>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {settings.ollama_enabled_models.map((modelName) => {
                  const label = modelName.startsWith("ollama/")
                    ? modelName.slice("ollama/".length)
                    : modelName;
                  return (
                    <span
                      key={modelName}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-600 dark:text-violet-400"
                    >
                      <HardDrive className="h-3 w-3" />
                      {label}
                      <button
                        type="button"
                        onClick={() => toggleModel(label)}
                        className="ml-0.5 text-violet-500/60 hover:text-danger transition"
                      >
                        ×
                      </button>
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Save */}
        <div className="flex items-center justify-end gap-3">
          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-br from-brand to-violet-600 px-4 py-2 text-sm font-medium text-white transition hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 shadow-lg shadow-brand/15"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {saving ? "Saving…" : "Save Settings"}
          </button>
        </div>
      </form>
    </div>
  );
}
