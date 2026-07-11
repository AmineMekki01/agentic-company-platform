import { useEffect, useMemo, useState } from "react";
import { Brain, Search, Trash2, X } from "lucide-react";
import { api, type AgentMemoryOut } from "@/lib/api";

interface MemoryPanelProps {
  agentSlug: string;
  agentName: string;
  onClose: () => void;
}

export default function MemoryPanel({ agentSlug, agentName, onClose }: MemoryPanelProps) {
  const [memories, setMemories] = useState<AgentMemoryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const filteredMemories = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return memories;
    return memories.filter(
      (m) =>
        m.content.toLowerCase().includes(q) ||
        m.category.toLowerCase().includes(q) ||
        (m.tags ?? []).some((tag) => tag.toLowerCase().includes(q))
    );
  }, [memories, search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getAgentMemories(agentSlug)
      .then((data) => {
        if (!cancelled) setMemories(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load what this agent remembers.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [agentSlug]);

  const handleDelete = async (memoryId: string) => {
    setDeletingId(memoryId);
    try {
      await api.deleteAgentMemory(agentSlug, memoryId);
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    } catch {
      setError("Couldn't delete that memory. Try again.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="animate-scale-in flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl border border-line/80 bg-card p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-brand" />
            <h3 className="text-lg font-semibold text-primary">What {agentName} remembers about you</h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-tertiary hover:bg-hover hover:text-secondary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <p className="mb-4 text-sm text-secondary">
          These are things learned from your conversations. Delete anything that's wrong or you'd
          rather it not remember.
        </p>

        {error && (
          <div className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{error}</div>
        )}

        {memories.length > 0 && (
          <div className="mb-3 flex items-center gap-2 rounded-xl border border-line bg-hover/70 px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-tertiary" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search memories…"
              className="w-full bg-transparent text-sm text-primary placeholder:text-tertiary focus:outline-none"
            />
          </div>
        )}

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="py-8 text-center text-sm text-tertiary">Loading…</div>
          ) : memories.length === 0 ? (
            <div className="py-8 text-center text-sm text-tertiary">Nothing remembered yet.</div>
          ) : filteredMemories.length === 0 ? (
            <div className="py-8 text-center text-sm text-tertiary">No memories match "{search}".</div>
          ) : (
            <ul className="space-y-2">
              {filteredMemories.map((m) => (
                <li
                  key={m.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-line bg-hover/70 px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-primary">{m.content}</p>
                    <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-tertiary">
                      <span className="rounded-full bg-canvas px-2 py-0.5">{m.category}</span>
                      {m.status === "superseded" && (
                        <span className="rounded-full bg-canvas px-2 py-0.5" title="No longer current, kept as history">
                          past
                        </span>
                      )}
                      {(m.tags ?? []).map((tag) => (
                        <span key={tag} className="rounded-full bg-canvas px-2 py-0.5">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(m.id)}
                    disabled={deletingId === m.id}
                    className="shrink-0 rounded-lg p-1.5 text-tertiary hover:bg-danger-soft hover:text-danger disabled:opacity-50"
                    aria-label="Forget this"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
