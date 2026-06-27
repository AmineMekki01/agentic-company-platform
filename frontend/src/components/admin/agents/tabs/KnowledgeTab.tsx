import type { AgentSetting, KnowledgeSource, UploadSettings } from "@/lib/api";

interface Props {
  selected: AgentSetting;
  setSelected: (a: AgentSetting) => void;
  sources: KnowledgeSource[];
  uploadSettings: UploadSettings | null;
}

export default function KnowledgeTab({ selected, setSelected, sources, uploadSettings }: Props) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <label className="block">
          <span className="text-xs font-medium text-secondary">Retrieval Top-K (1-20)</span>
          <input
            type="number"
            min={1}
            max={20}
            value={selected.retrieval_top_k}
            onChange={(e) =>
              setSelected({
                ...selected,
                retrieval_top_k: Math.min(20, Math.max(1, parseInt(e.target.value || "5", 10))),
              })
            }
            className="w-full bg-canvas border border-line rounded-lg px-3 py-2 text-sm mt-1 text-primary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition"
          />
          <p className="text-xs text-tertiary mt-1">
            Number of chunks retrieved per query.
          </p>
        </label>
      </div>

      <label
        className={`flex items-center gap-2 rounded-lg border border-line bg-canvas px-3 py-2.5 ${uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}
        title={
          uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket
            ? ""
            : "Go to Upload Settings and enable file uploads with an S3 connector + bucket first."
        }
      >
        <input
          type="checkbox"
          checked={selected.allow_uploads !== false}
          onChange={(e) => setSelected({ ...selected, allow_uploads: e.target.checked })}
          disabled={!(uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket)}
          className="accent-brand"
        />
        <span>
          <span className="block text-sm font-medium text-primary">Allow file uploads</span>
          <span className="block text-xs text-tertiary">
            {uploadSettings?.enabled && uploadSettings?.s3_connector_id && uploadSettings?.s3_bucket
              ? "Shows the attach button in chat when this agent is selected."
              : "Upload Settings must be configured (S3 connector + bucket) before enabling."}
          </span>
        </span>
      </label>

      <div>
        <h3 className="text-sm font-medium text-secondary mb-1">Connected Knowledge Sources</h3>
        <p className="text-xs text-tertiary mb-3">
          Select the knowledge sources this agent can retrieve from. Retrieval is automatically enabled when at least one source is connected.
        </p>
        <div className="space-y-1 max-h-64 overflow-y-auto bg-canvas border border-line rounded-lg px-3 py-2">
          {sources.length === 0 && (
            <p className="text-xs text-tertiary">No sources configured. Go to Knowledge Sources to add documents.</p>
          )}
          {sources.map((s) => {
            const checked = (selected.connected_sources || []).includes(s.id);
            return (
              <label key={s.id} className="flex items-center gap-2 text-sm text-secondary cursor-pointer hover:bg-hover rounded-md px-1 py-0.5 transition">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const current = selected.connected_sources || [];
                    const next = checked
                      ? current.filter((x) => x !== s.id)
                      : [...current, s.id];
                    setSelected({ ...selected, connected_sources: next });
                  }}
                  className="accent-brand"
                />
                <span>{s.name}</span>
                <span className="text-xs text-tertiary">({s.slug})</span>
              </label>
            );
          })}
        </div>
      </div>

      {(selected.connected_sources || []).length > 0 && (
        <div className="bg-brand/10 border border-brand/20 rounded-lg px-3 py-2">
          <p className="text-xs text-brand">
            <strong>{(selected.connected_sources || []).length}</strong> source(s) connected. Retrieval is active.
          </p>
        </div>
      )}
    </div>
  );
}
