import { Workflow } from "lucide-react";
import type { AgentSetting, DbUser, ModelOption } from "@/lib/api";
import { formatUserLabel } from "../agentUtils";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  users: DbUser[];
  models: ModelOption[];
}

export default function OverviewTab({ selected, setSelected, users, models }: Props) {
  const providers = [...new Set(models.map((m) => m.provider))];

  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <label className="block">
          <span className="text-xs font-medium text-secondary">Name</span>
          <input
            value={selected.name || ""}
            onChange={(e) => setSelected({ ...selected, name: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-secondary">LLM Model</span>
          <select
            value={selected.llm_model || "gpt-5.4-nano"}
            onChange={(e) => setSelected({ ...selected, llm_model: e.target.value })}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          >
            {providers.map((prov) => (
              <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                {models.filter((m) => m.provider === prov).map((m) => (
                  <option key={m.name} value={m.name}>{m.label}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      </div>

      <label className="block">
        <span className="text-xs font-medium text-secondary">Description</span>
        <textarea
          value={selected.description || ""}
          onChange={(e) => setSelected({ ...selected, description: e.target.value })}
          rows={2}
          className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
        />
      </label>

      <label className="block">
        <span className="text-xs font-medium text-secondary">Owner</span>
        <select
          value={selected.created_by || ""}
          onChange={(e) => setSelected({ ...selected, created_by: e.target.value })}
          className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
        >
          <option value="">Keep existing owner</option>
          {users.map((u) => (
            <option key={u.id} value={u.email}>
              {formatUserLabel(u)} — {u.email}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-xs font-medium text-secondary">Agent Type</span>
        <select
          value={selected.agent_type || "standard"}
          onChange={(e) => {
            const newType = e.target.value;
            const updates: Partial<AgentSetting> = { agent_type: newType };
            if (newType === "deep_research" && !selected.research_config) {
              updates.research_config = {
                max_researcher_iterations: 5,
                max_concurrent_research_units: 3,
                max_react_tool_calls: 8,
                clarification_model: "gpt-5.4-nano",
                research_model: "gpt-5.4",
                compression_model: "gpt-5.4",
                final_report_model: "gpt-5.4",
                search_tools: ["web_search"],
                connected_sources: [],
              };
              updates.tools = ["web_search"];
              updates.web_search_enabled = true;
              updates.is_orchestrator = false;
              updates.is_router = false;
              updates.routes_to = [];
            }
            setSelected({ ...selected, ...updates });
          }}
          className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
        >
          <option value="standard">Standard Agent</option>
          <option value="deep_research">Deep Research Agent</option>
        </select>
      </label>

      <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-line bg-canvas px-3 py-2.5">
        <input
          type="checkbox"
          checked={selected.memory_enabled || false}
          onChange={(e) => setSelected({ ...selected, memory_enabled: e.target.checked })}
          className="accent-brand"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Enable Memory</span>
          <span className="block text-xs text-tertiary">
            Remembers facts, preferences, and commitments across conversations, stays
            consistent with what it's been told (self-checks its own drafts against
            memory before sending), and can recall specific past exchanges.
          </span>
        </span>
      </label>

      <label className="flex items-center gap-2 cursor-pointer rounded-lg border border-line bg-canvas px-3 py-2.5">
        <input
          type="checkbox"
          checked={selected.emotions_enabled || false}
          onChange={(e) => {
            const emotionsEnabled = e.target.checked;
            setSelected({
              ...selected,
              emotions_enabled: emotionsEnabled,
              episodes_enabled: emotionsEnabled ? selected.episodes_enabled : false,
            });
          }}
          className="accent-brand"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Enable Emotions</span>
          <span className="block text-xs text-tertiary">
            This agent develops a persistent feeling toward each user based on your
            interactions, and reads the mood behind your current message - both
            subtly shape its tone without ever being stated explicitly.
          </span>
        </span>
      </label>

      <label
        className={`ml-6 flex items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2.5 ${
          selected.emotions_enabled ? "cursor-pointer" : "cursor-not-allowed opacity-50"
        }`}
      >
        <input
          type="checkbox"
          checked={selected.episodes_enabled || false}
          disabled={!selected.emotions_enabled}
          onChange={(e) => setSelected({ ...selected, episodes_enabled: e.target.checked })}
          className="accent-brand"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Remember significant moments</span>
          <span className="block text-xs text-tertiary">
            Recalls specific past exchanges that were emotionally significant - a
            genuine rupture, not just an enthusiastic one. Requires Emotions.
          </span>
        </span>
      </label>

      {selected.agent_type === "deep_research" && selected.research_config && (
        <div className="rounded-lg border border-brand/20 bg-brand/10 p-4 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-brand">
            <Workflow className="h-4 w-4" />
            Deep Research Configuration
          </div>

          <div>
            <span className="text-xs font-medium text-secondary">Search Tools</span>
            <div className="mt-2 flex flex-wrap gap-3">
              <label className="flex items-center gap-1.5 text-sm text-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.research_config.search_tools.includes("web_search")}
                  onChange={() => {
                    const rc = { ...selected.research_config! };
                    const has = rc.search_tools.includes("web_search");
                    rc.search_tools = has
                      ? rc.search_tools.filter((t) => t !== "web_search")
                      : [...rc.search_tools, "web_search"];
                    setSelected({ ...selected, research_config: rc });
                  }}
                  className="accent-brand"
                />
                <span>Web Search (Tavily)</span>
              </label>
              <label className="flex items-center gap-1.5 text-sm text-secondary cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.research_config.search_tools.includes("retrieve")}
                  onChange={() => {
                    const rc = { ...selected.research_config! };
                    const has = rc.search_tools.includes("retrieve");
                    rc.search_tools = has
                      ? rc.search_tools.filter((t) => t !== "retrieve")
                      : [...rc.search_tools, "retrieve"];
                    setSelected({ ...selected, research_config: rc });
                  }}
                  className="accent-brand"
                />
                <span>Internal Knowledge Base</span>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-secondary">Max Research Iterations</span>
              <input
                type="number"
                min={1}
                max={10}
                value={selected.research_config.max_researcher_iterations}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, max_researcher_iterations: parseInt(e.target.value) || 5 };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-secondary">Max Concurrent Researchers</span>
              <input
                type="number"
                min={1}
                max={10}
                value={selected.research_config.max_concurrent_research_units}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, max_concurrent_research_units: parseInt(e.target.value) || 3 };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium text-secondary">Max Tool Calls / Researcher</span>
              <input
                type="number"
                min={1}
                max={20}
                value={selected.research_config.max_react_tool_calls}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, max_react_tool_calls: parseInt(e.target.value) || 8 };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-medium text-secondary">Clarification Model</span>
              <select
                value={selected.research_config.clarification_model}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, clarification_model: e.target.value };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              >
                {providers.map((prov) => (
                  <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                    {models.filter((m) => m.provider === prov).map((m) => (
                      <option key={m.name} value={m.name}>{m.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-secondary">Research Model</span>
              <select
                value={selected.research_config.research_model}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, research_model: e.target.value };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              >
                {providers.map((prov) => (
                  <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                    {models.filter((m) => m.provider === prov).map((m) => (
                      <option key={m.name} value={m.name}>{m.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-secondary">Compression Model</span>
              <select
                value={selected.research_config.compression_model}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, compression_model: e.target.value };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              >
                {providers.map((prov) => (
                  <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                    {models.filter((m) => m.provider === prov).map((m) => (
                      <option key={m.name} value={m.name}>{m.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-secondary">Final Report Model</span>
              <select
                value={selected.research_config.final_report_model}
                onChange={(e) => {
                  const rc = { ...selected.research_config!, final_report_model: e.target.value };
                  setSelected({ ...selected, research_config: rc });
                }}
                className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
              >
                {providers.map((prov) => (
                  <optgroup key={prov} label={prov === "ollama" ? "Ollama (Local)" : prov.charAt(0).toUpperCase() + prov.slice(1)}>
                    {models.filter((m) => m.provider === prov).map((m) => (
                      <option key={m.name} value={m.name}>{m.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
          </div>
        </div>
      )}

      {selected.agent_type !== "deep_research" && (
        <label className="block">
          <span className="text-xs font-medium text-secondary">Instructions (System Prompt)</span>
          <textarea
            value={selected.system_prompt || ""}
            onChange={(e) => setSelected({ ...selected, system_prompt: e.target.value })}
            rows={5}
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
            placeholder="Define how this agent behaves, what it can do, and how it should respond..."
          />
        </label>
      )}
    </>
  );
}
