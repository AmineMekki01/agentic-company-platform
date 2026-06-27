import { Loader2, ThumbsUp } from "lucide-react";
import type { AgentFeedbackSummary, MessageFeedback } from "@/lib/api";

interface Props {
  feedbackSummary: AgentFeedbackSummary | null;
  feedbackList: MessageFeedback[];
  feedbackLoading: boolean;
  onSelectFeedback: (f: MessageFeedback) => void;
}

export default function FeedbackTab({ feedbackSummary, feedbackList, feedbackLoading, onSelectFeedback }: Props) {
  return (
    <div className="space-y-6">
      {feedbackSummary && (
        <div className="grid grid-cols-4 gap-4">
          <div className="rounded-xl border border-line bg-canvas p-4">
            <div className="text-xs font-medium text-tertiary uppercase tracking-wide">Total</div>
            <div className="mt-1 text-2xl font-bold text-primary">{feedbackSummary.total}</div>
          </div>
          <div className="rounded-xl border border-success/20 bg-success-soft/50 p-4">
            <div className="text-xs font-medium text-success uppercase tracking-wide">Thumbs Up</div>
            <div className="mt-1 text-2xl font-bold text-success">{feedbackSummary.thumbs_up}</div>
          </div>
          <div className="rounded-xl border border-danger/20 bg-danger-soft/50 p-4">
            <div className="text-xs font-medium text-danger uppercase tracking-wide">Thumbs Down</div>
            <div className="mt-1 text-2xl font-bold text-danger">{feedbackSummary.thumbs_down}</div>
          </div>
          <div className="rounded-xl border border-line bg-canvas p-4">
            <div className="text-xs font-medium text-tertiary uppercase tracking-wide">Positive Rate</div>
            <div className="mt-1 text-2xl font-bold text-primary">{feedbackSummary.up_rate_pct}%</div>
          </div>
        </div>
      )}

      {feedbackLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
        </div>
      ) : feedbackList.length === 0 ? (
        <div className="rounded-lg border border-line bg-canvas/70 px-6 py-8 text-center">
          <p className="text-sm text-tertiary">No feedback yet for this agent.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-line overflow-hidden">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-canvas text-xs uppercase tracking-wide text-tertiary">
              <tr>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">User</th>
                <th className="px-4 py-2 font-medium">Rating</th>
                <th className="px-4 py-2 font-medium">Comment</th>
                <th className="px-4 py-2 font-medium">Screenshot</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {feedbackList.map((f) => (
                <tr key={f.id} className="hover:bg-hover/70 transition cursor-pointer" onClick={() => onSelectFeedback(f)}>
                  <td className="px-4 py-2.5 text-secondary whitespace-nowrap">
                    {new Date(f.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-secondary">{f.user_id.slice(0, 8)}…</td>
                  <td className="px-4 py-2.5">
                    {f.thumbs_up ? (
                      <span className="inline-flex items-center gap-1 rounded-md bg-success-soft px-2 py-0.5 text-xs text-success">
                        <ThumbsUp className="h-3 w-3" /> Up
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-md bg-danger-soft px-2 py-0.5 text-xs text-danger">
                        <ThumbsUp className="h-3 w-3" /> Down
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-secondary max-w-xs truncate">
                    {f.comment || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    {f.screenshot_attachment_id ? (
                      <span className="text-xs text-brand">Yes</span>
                    ) : (
                      <span className="text-xs text-tertiary">No</span>
                    )}
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
