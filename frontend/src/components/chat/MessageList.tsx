import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, FileText, Loader2, Paperclip, User as UserIcon } from "lucide-react";

import type { Agent } from "@/lib/api";

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
  role: "user" | "assistant";
  content: string;
  agent_id: string | null;
  streaming?: boolean;
  sources?: SourceInfo[];
  step?: string;
  attachments?: AttachmentInfo[];
  draft?: boolean;
}

interface MessageListProps {
  messages: DisplayMessage[];
  agents: Agent[];
  emptyState: React.ReactNode;
  renderAction?: (message: DisplayMessage) => React.ReactNode;
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
}: {
  m: DisplayMessage;
  renderAction?: (message: DisplayMessage) => React.ReactNode;
}) {
  const [highlightedRank, setHighlightedRank] = useState<number | null>(null);


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
          {m.step === "searching" && "Searching sources…"}
          {m.step === "thinking" && "Thinking…"}
          {m.step === "verifying" && "Verifying answer…"}
          {(!m.step || m.step === "generating") && "Generating…"}
        </span>
      )}
      {dedupedSources.length > 0 && (
        <div className="mt-4 rounded-xl border border-zinc-700/40 bg-zinc-800/30 px-4 py-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-zinc-400 uppercase tracking-wide">
            <FileText className="h-3.5 w-3.5" />
            Sources
          </div>
          <ul className="space-y-0.5">
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
        </div>
      )}
      {renderAction && !m.streaming && (
        <div className="mt-3">{renderAction(m)}</div>
      )}
    </div>
  );
}

export default function MessageList({ messages, agents, emptyState, renderAction }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <div className="flex flex-1 items-center justify-center">{emptyState}</div>;
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-8 px-4 py-8">
        {messages.map((m) => (
          <div key={m.id} className="flex gap-3.5 group">
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${
                m.role === "user"
                  ? "bg-gradient-to-br from-zinc-600 to-zinc-700"
                  : "bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/15"
              }`}
            >
              {m.role === "user" ? (
                <UserIcon className="h-4 w-4 text-zinc-200" />
              ) : (
                <Bot className="h-4 w-4 text-white" />
              )}
            </div>

            <div className="min-w-0 flex-1 pt-0.5">
              <div className="mb-1.5 flex items-baseline gap-2">
                <span className="text-xs font-semibold text-zinc-300">
                  {m.role === "user" ? "You" : agentName(agents, m.agent_id)}
                </span>
                {m.role === "assistant" && m.agent_id && (
                  <span className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-indigo-300">
                    @{m.agent_id}
                  </span>
                )}
                {m.role === "assistant" && m.draft && (
                  <span className="rounded-md bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-400">
                    Draft
                  </span>
                )}
              </div>

              {m.role === "user" ? (
                <div>
                  {m.attachments && m.attachments.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-2">
                      {m.attachments.map((att, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800/60 px-2 py-1 text-xs text-zinc-300"
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
              ) : (
                <AssistantMessage m={m} renderAction={renderAction} />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
