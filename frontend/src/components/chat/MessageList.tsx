import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, ChevronDown, ChevronRight, FileText, Loader2, Paperclip, ThumbsUp, ThumbsDown, User as UserIcon, ArrowRight } from "lucide-react";

import type { Agent } from "@/lib/api";
import FeedbackModal from "./FeedbackModal";

export interface SourceInfo {
  rank: number;
  title: string;
  id: string;
  url: string | null;
}

export interface AttachmentInfo {
  filename: string;
  extractedText?: string | null;
}

export interface DisplayMessage {
  id: string;
  serverId?: string;
  role: "user" | "assistant";
  content: string;
  agent_id: string | null;
  streaming?: boolean;
  sources?: SourceInfo[];
  step?: string;
  attachments?: AttachmentInfo[];
  draft?: boolean;
  awaitingClarification?: boolean;
}

interface MessageListProps {
  messages: DisplayMessage[];
  agents: Agent[];
  emptyState: React.ReactNode;
  renderAction?: (message: DisplayMessage) => React.ReactNode;
  conversationId?: string;
  feedbackMap?: Record<string, { thumbs_up: boolean }>;
  onFeedbackSubmitted?: (messageId: string, thumbsUp: boolean) => void;
}

function agentName(agents: Agent[], slug: string | null): string {
  if (!slug) return "Assistant";
  return agents.find((a) => a.slug === slug)?.name ?? slug;
}


function linkifyCitations(content: string, rankMap: Map<number, number>): string {
  return content.replace(/\[(\d+)\]/g, (_, n) => {
    const rank = parseInt(n, 10);
    const canonical = rankMap.get(rank);
    if (canonical !== undefined) return `[${canonical}](#cite-${canonical})`;
    return `[${n}]`;
  });
}

function AssistantMessage({
  m,
  renderAction,
  conversationId,
  hasFeedback,
  feedbackUp,
  onFeedbackSubmitted,
}: {
  m: DisplayMessage;
  renderAction?: (message: DisplayMessage) => React.ReactNode;
  conversationId?: string;
  hasFeedback?: boolean;
  feedbackUp?: boolean;
  onFeedbackSubmitted?: (messageId: string, thumbsUp: boolean) => void;
}) {
  const [highlightedRank, setHighlightedRank] = useState<number | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalInitialUp, setModalInitialUp] = useState(true);
  const [sourcesExpanded, setSourcesExpanded] = useState(false);


  const seenTitles = new Set<string>();
  const dedupedSources: SourceInfo[] = [];
  const rankMap = new Map<number, number>(); 
  
  for (const s of m.sources ?? []) {
    if (!seenTitles.has(s.title)) {
      seenTitles.add(s.title);
      const canonicalRank = dedupedSources.length + 1;
      rankMap.set(s.rank, canonicalRank);
      dedupedSources.push({ ...s, rank: canonicalRank });
    } else {
      const canonical = dedupedSources.find((d) => d.title === s.title);
      if (canonical) {
        rankMap.set(s.rank, canonical.rank);
      }
    }
  }

  const processed = linkifyCitations(m.content, rankMap);

  return (
    <div className="prose-chat text-sm leading-relaxed text-zinc-200">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const match = typeof href === "string" ? href.match(/^#cite-(\d+)$/) : null;
            if (match) {
              const rank = parseInt(match[1], 10);
              const canonical = rankMap.get(rank) ?? rank;
              return (
                <button
                  onClick={() => setHighlightedRank(canonical)}
                  className="inline-flex items-center text-indigo-400 hover:text-indigo-300 font-medium text-xs align-super cursor-pointer"
                  title={`Jump to source [${canonical}]`}
                >
                  [{canonical}]
                </button>
              );
            }
            return <a href={href}>{children}</a>;
          },
        }}
      >
        {processed || (m.streaming ? "…" : "")}
      </ReactMarkdown>
      {m.streaming && (
        <span className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-2.5 py-1 text-[11px] font-medium text-indigo-300 border border-indigo-500/20">
          <Loader2 className="h-3 w-3 animate-spin" />
          {m.step === "routing" && "Routing…"}
          {m.step === "clarifying" && "Analyzing request…"}
          {m.step === "planning" && "Planning research…"}
          {m.step === "supervising" && "Coordinating research…"}
          {m.step === "searching" && "Searching sources…"}
          {m.step === "compressing" && "Synthesizing findings…"}
          {m.step === "writing_report" && "Writing report…"}
          {m.step === "resuming" && "Continuing research…"}
          {m.step === "thinking" && "Thinking…"}
          {m.step === "verifying" && "Verifying answer…"}
          {(!m.step || m.step === "generating") && "Generating…"}
        </span>
      )}
      {dedupedSources.length > 0 && (
        <div className="mt-3">
          <button
            onClick={() => setSourcesExpanded((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-700/40 bg-zinc-800/30 px-2.5 py-1.5 text-[11px] font-medium text-zinc-400 transition hover:bg-zinc-800/50 hover:text-zinc-300"
          >
            <FileText className="h-3.5 w-3.5" />
            {sourcesExpanded ? "Hide" : "Show"} {dedupedSources.length} source{dedupedSources.length > 1 ? "s" : ""}
            {sourcesExpanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>
          {sourcesExpanded && (
            <ul className="mt-2 space-y-0.5 rounded-xl border border-zinc-700/40 bg-zinc-800/30 px-3 py-2.5">
              {dedupedSources.map((s) => {
                const content = (
                  <>
                    <span className="mr-1 text-indigo-400">[{s.rank}]</span>
                    {s.title}
                  </>
                );
                return (
                  <li
                    key={s.id}
                    className={`text-xs rounded-md px-2 py-1 transition ${
                      highlightedRank === s.rank
                        ? "bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                        : "text-zinc-500 border border-transparent hover:bg-zinc-700/30"
                    }`}
                  >
                    {s.url ? (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:text-indigo-300 hover:underline"
                        title={s.url}
                      >
                        {content}
                      </a>
                    ) : (
                      <span>{content}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      {renderAction && !m.streaming && (
        <div className="mt-3">{renderAction(m)}</div>
      )}
      {!m.streaming && conversationId && (
        <div className="mt-2 flex items-center gap-2">
          <button
            onClick={() => {
              setModalInitialUp(true);
              setShowModal(true);
            }}
            className={`rounded-lg p-1.5 transition ${
              hasFeedback && feedbackUp
                ? "text-emerald-400 bg-emerald-500/10"
                : "text-zinc-500 opacity-40 hover:opacity-100 hover:text-zinc-300 hover:bg-zinc-800"
            }`}
            title="Thumbs up"
          >
            <ThumbsUp className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              setModalInitialUp(false);
              setShowModal(true);
            }}
            className={`rounded-lg p-1.5 transition ${
              hasFeedback && !feedbackUp
                ? "text-rose-400 bg-rose-500/10"
                : "text-zinc-500 opacity-40 hover:opacity-100 hover:text-zinc-300 hover:bg-zinc-800"
            }`}
            title="Thumbs down"
          >
            <ThumbsDown className="h-4 w-4" />
          </button>
        </div>
      )}
      {showModal && conversationId && (
        <FeedbackModal
          conversationId={conversationId}
          messageId={m.serverId || m.id}
          initialThumbsUp={modalInitialUp}
          onClose={() => setShowModal(false)}
          onSubmitted={() => {
            setShowModal(false);
            onFeedbackSubmitted?.(m.serverId || m.id, modalInitialUp);
          }}
        />
      )}
    </div>
  );
}

export default function MessageList({
  messages,
  agents,
  emptyState,
  renderAction,
  conversationId,
  feedbackMap,
  onFeedbackSubmitted,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <div className="flex flex-1 items-center justify-center">{emptyState}</div>;
  }

  // Build a map of previous assistant agent per message index
  const prevAssistantAgents: (string | null)[] = [];
  let lastAgent: string | null = null;
  for (const m of messages) {
    prevAssistantAgents.push(lastAgent);
    if (m.role === "assistant" && m.agent_id) {
      lastAgent = m.agent_id;
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        {messages.map((m, idx) => {
          const prevAgent = prevAssistantAgents[idx];
          const isHandoff = m.role === "assistant" && !!m.agent_id && prevAgent !== null && prevAgent !== m.agent_id;
          return (
            <div key={m.id} className="group animate-fade-in-up">
              {isHandoff && (
                <div className="mb-3 flex w-full items-center gap-2">
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent via-zinc-700/60 to-transparent" />
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-zinc-900/80 border border-zinc-800/60 px-3 py-1 text-[10px] font-medium uppercase tracking-wide text-zinc-500 backdrop-blur-sm">
                    <ArrowRight className="h-3 w-3 text-indigo-400" />
                    Handed off to {agentName(agents, m.agent_id)}
                  </span>
                  <div className="h-px flex-1 bg-gradient-to-r from-transparent via-zinc-700/60 to-transparent" />
                </div>
              )}
              {m.role === "user" ? (
                <div className="flex flex-row-reverse gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-zinc-600 to-zinc-700 ring-1 ring-white/5">
                    <UserIcon className="h-4 w-4 text-zinc-200" />
                  </div>
                  <div className="min-w-0 max-w-[80%] pt-0.5">
                    <div className="mb-1.5 flex items-baseline justify-end gap-2">
                      <span className="text-xs font-semibold text-zinc-300">You</span>
                    </div>
                    <div className="rounded-2xl rounded-tr-md bg-zinc-800/60 border border-zinc-700/40 px-4 py-3 shadow-sm">
                      {m.attachments && m.attachments.length > 0 && (
                        <div className="mb-2 flex flex-wrap gap-2">
                          {m.attachments.map((att, i) => (
                            <span
                              key={i}
                              className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-700/60 px-2 py-1 text-xs text-zinc-300"
                            >
                              <Paperclip className="h-3 w-3 text-zinc-500" />
                              {att.filename}
                            </span>
                          ))}
                        </div>
                      )}
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
                        {m.content}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/15 ring-1 ring-white/5">
                    <Bot className="h-4 w-4 text-white" />
                  </div>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="mb-1.5 flex items-baseline gap-2">
                      <span className="text-xs font-semibold text-zinc-300">
                        {agentName(agents, m.agent_id)}
                      </span>
                      {m.agent_id && (
                        <span className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-indigo-300">
                          @{m.agent_id}
                        </span>
                      )}
                      {m.draft && (
                        <span className="rounded-md bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-400">
                          Draft
                        </span>
                      )}
                    </div>
                    <AssistantMessage
                      m={m}
                      renderAction={renderAction}
                      conversationId={conversationId}
                      hasFeedback={!!feedbackMap?.[m.serverId || m.id]}
                      feedbackUp={feedbackMap?.[m.serverId || m.id]?.thumbs_up}
                      onFeedbackSubmitted={onFeedbackSubmitted}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
