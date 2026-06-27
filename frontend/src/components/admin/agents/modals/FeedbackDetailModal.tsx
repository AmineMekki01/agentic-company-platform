import { useState } from "react";
import { ChevronUp, ChevronDown, Eye, FileText, MessageSquare, Rocket, ThumbsUp, Wrench, X } from "lucide-react";
import type { MessageFeedback } from "@/lib/api";

interface Props {
  feedback: MessageFeedback;
  onClose: () => void;
}

export default function FeedbackDetailModal({ feedback, onClose }: Props) {
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<number>>(new Set());
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  const toggleToolCall = (idx: number) => {
    setExpandedToolCalls((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleSource = (idx: number) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-canvas border border-line rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <div className="flex items-center gap-3">
            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${feedback.thumbs_up ? "bg-success-soft" : "bg-danger-soft"}`}>
              <ThumbsUp className={`h-4 w-4 ${feedback.thumbs_up ? "text-success" : "text-danger"}`} />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-primary">
                {feedback.thumbs_up ? "Thumbs Up" : "Thumbs Down"} — {feedback.user_id.slice(0, 8)}…
              </h3>
              <p className="text-xs text-tertiary">{new Date(feedback.created_at).toLocaleString()}</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-tertiary hover:bg-hover hover:text-primary transition">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {feedback.comment && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <MessageSquare className="h-3.5 w-3.5" />
                User Comment
              </div>
              <div className="bg-card border border-line/60 rounded-xl px-3 py-2 text-sm text-secondary">
                {feedback.comment}
              </div>
            </div>
          )}

          {feedback.conversation_actions && feedback.conversation_actions.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <Rocket className="h-3.5 w-3.5" />
                Conversation Actions ({feedback.conversation_actions.length})
              </div>
              <div className="space-y-2">
                {feedback.conversation_actions.map((action, i) => (
                  <div key={i} className="bg-card border border-line/60 rounded-xl px-3 py-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-bold text-success bg-success-soft rounded px-1.5 py-0.5 uppercase tracking-wide">
                        {action.type.replace(/_/g, " ")}
                      </span>
                      {action.ticket_key && (
                        <a
                          href={action.ticket_url || "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-semibold text-brand hover:text-brand transition"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {action.ticket_key}
                        </a>
                      )}
                    </div>
                    {action.summary && <p className="text-xs text-secondary">{action.summary}</p>}
                    {action.raw && !action.summary && <p className="text-xs text-tertiary font-mono">{action.raw}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {feedback.conversation_snapshot && feedback.conversation_snapshot.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <MessageSquare className="h-3.5 w-3.5" />
                Conversation Snapshot
              </div>
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {feedback.conversation_snapshot.map((msg) => (
                  <div key={msg.id} className={`rounded-lg px-3 py-2 text-sm border ${msg.role === "assistant" ? "bg-brand/10 border-brand/10 text-secondary" : "bg-card border-line text-secondary"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className={`text-[10px] font-bold uppercase tracking-wide ${msg.role === "assistant" ? "text-brand" : "text-tertiary"}`}>
                        {msg.role}
                      </span>
                      {msg.agent_id && <span className="text-[10px] text-tertiary">• {msg.agent_id}</span>}
                    </div>
                    <p className="text-sm text-secondary whitespace-pre-wrap">{msg.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {feedback.tool_calls_log && feedback.tool_calls_log.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <Wrench className="h-3.5 w-3.5" />
                Tool Calls
              </div>
              <div className="space-y-2">
                {feedback.tool_calls_log.map((tc, i) => {
                  const expanded = expandedToolCalls.has(i);
                  const resultStr = tc.result !== undefined ? JSON.stringify(tc.result) : "";
                  return (
                    <div key={i} className="bg-card border border-line/60 rounded-xl px-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-xs font-semibold text-brand">{tc.tool || "unknown tool"}</div>
                        {resultStr.length > 200 && (
                          <button
                            onClick={() => toggleToolCall(i)}
                            className="flex items-center gap-0.5 text-[10px] text-tertiary hover:text-secondary transition"
                          >
                            {expanded ? (
                              <><ChevronUp className="h-3 w-3" /> Less</>
                            ) : (
                              <><ChevronDown className="h-3 w-3" /> More</>
                            )}
                          </button>
                        )}
                      </div>
                      <div className="text-[11px] text-tertiary font-mono bg-canvas rounded px-2 py-1 overflow-x-auto">
                        {tc.tool === "retrieve" && tc.args?.sources === null ? (
                          <div>
                            <span className="text-[10px] text-warning/80 bg-warning-soft rounded px-1.5 py-0.5">sources: agent defaults</span>
                            <pre className="mt-1">{JSON.stringify({ ...tc.args, sources: undefined }, null, 2)}</pre>
                          </div>
                        ) : (
                          JSON.stringify(tc.args || {}, null, 2)
                        )}
                      </div>
                      {tc.result !== undefined && (
                        <div className="mt-1.5 text-[11px] text-secondary font-mono bg-canvas rounded px-2 py-1 overflow-x-auto whitespace-pre-wrap">
                          {expanded ? resultStr : resultStr.slice(0, 200) + (resultStr.length > 200 ? "…" : "")}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {feedback.retrieved_sources && feedback.retrieved_sources.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <FileText className="h-3.5 w-3.5" />
                Retrieved Sources ({feedback.retrieved_sources.length})
              </div>
              <div className="space-y-2">
                {feedback.retrieved_sources.map((src, i) => {
                  const expanded = expandedSources.has(i);
                  return (
                    <div
                      key={i}
                      className="bg-card border border-line/60 rounded-xl px-3 py-2 cursor-pointer hover:border-line transition"
                      onClick={() => toggleSource(i)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[10px] font-bold text-brand bg-brand/10 rounded px-1.5 py-0.5 shrink-0">[{src.rank}]</span>
                          <span className="text-[11px] font-medium text-secondary truncate">{src.title || "Untitled"}</span>
                        </div>
                        {expanded ? (
                          <ChevronUp className="h-3 w-3 text-tertiary shrink-0" />
                        ) : (
                          <ChevronDown className="h-3 w-3 text-tertiary shrink-0" />
                        )}
                      </div>
                      {src.url && <div className="text-[10px] text-tertiary truncate mt-1">{src.url}</div>}
                      <div className="text-[10px] text-tertiary font-mono mt-0.5">ID: {src.id?.slice(0, 8)}…</div>
                      {expanded && (
                        <div className="mt-2 pt-2 border-t border-line">
                          <a
                            href={src.url || "#"}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-brand hover:text-brand transition mb-1.5 inline-block"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Open source →
                          </a>
                          <div className="text-[10px] text-tertiary font-mono bg-canvas rounded px-2 py-1.5 overflow-x-auto whitespace-pre-wrap">
                            Source: {src.title}
                            <br />
                            ID: {src.id}
                            {src.url && <><br />URL: {src.url}</>}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {feedback.screenshot_attachment_id && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-secondary mb-1.5">
                <Eye className="h-3.5 w-3.5" />
                Screenshot
              </div>
              <div className="text-xs text-tertiary">
                Attachment ID: {feedback.screenshot_attachment_id}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
