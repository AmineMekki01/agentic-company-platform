import { Loader2, History, Eye, RotateCcw } from "lucide-react";
import type { AgentVersion } from "@/lib/api";
import { formatDateTime } from "../agentUtils";

interface Props {
  versions: AgentVersion[];
  restoring: boolean;
  onViewVersion: (versionId: string) => void;
  onRestoreVersion: (versionId: string) => void;
}

export default function VersionsTab({ versions, restoring, onViewVersion, onRestoreVersion }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-primary">Version History</h3>
        {restoring && <Loader2 className="h-4 w-4 animate-spin text-tertiary" />}
      </div>

      {versions.length === 0 ? (
        <div className="text-center py-10">
          <History className="mx-auto h-8 w-8 text-tertiary mb-2" />
          <p className="text-sm text-tertiary">No versions yet.</p>
          <p className="text-xs text-tertiary mt-1">Publish this agent to create the first version.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-line overflow-hidden">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
              <tr>
                <th className="px-4 py-2 font-medium">Version</th>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Author</th>
                <th className="px-4 py-2 font-medium">Notes</th>
                <th className="px-4 py-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-card">
              {versions.map((v) => (
                <tr key={v.id} className="hover:bg-hover/70 transition">
                  <td className="px-4 py-2.5 font-mono text-xs text-secondary">
                    <button
                      onClick={() => onViewVersion(v.id)}
                      className="hover:text-brand transition"
                    >
                      v{v.version_number}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{formatDateTime(v.created_at)}</td>
                  <td className="px-4 py-2.5 text-secondary">{v.created_by || "—"}</td>
                  <td className="px-4 py-2.5 text-secondary max-w-xs truncate">{v.notes || "—"}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button
                      onClick={() => onViewVersion(v.id)}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-secondary hover:bg-hover hover:text-primary transition mr-2"
                    >
                      <Eye className="h-3 w-3" />
                      View
                    </button>
                    <button
                      onClick={() => onRestoreVersion(v.id)}
                      disabled={restoring}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-secondary hover:bg-hover hover:text-primary transition disabled:opacity-40"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Restore
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
