import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, FileText, User as UserIcon } from "lucide-react";

import type { Agent } from "@/lib/api";

export interface SourceInfo {
  rank: number;
  title: string;
  id: string;
  url: string | null;
}

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  agent_id: string | null;
  streaming?: boolean;
  sources?: SourceInfo[];
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

/** Convert inline citation markers [1] … [N] into markdown links.
 *  rankMap maps original rank -> canonical rank; if absent, citations are linked directly. */
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

  // Deduplicate sources by title - keep first occurrence and remap later ranks
  const seenTitles = new Set<string>();
  const dedupedSources: SourceInfo[] = [];
  const rankMap = new Map<number, number>(); // original rank -> canonical rank

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
        <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-indigo-400 align-text-bottom" />
      )}
      {dedupedSources.length > 0 && (
        <div className="mt-3 rounded-lg border border-zinc-700/50 bg-zinc-800/40 px-3 py-2">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-400">
            <FileText className="h-3 w-3" />
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
                  className={`text-xs rounded px-1 py-0.5 transition ${
                    highlightedRank === s.rank
                      ? "bg-indigo-600/20 text-indigo-300"
                      : "text-zinc-500"
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
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        {messages.map((m) => (
          <div key={m.id} className="flex gap-3">
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                m.role === "user" ? "bg-zinc-700" : "bg-indigo-600"
              }`}
            >
              {m.role === "user" ? (
                <UserIcon className="h-4 w-4 text-zinc-200" />
              ) : (
                <Bot className="h-4 w-4 text-white" />
              )}
            </div>

            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-baseline gap-2">
                <span className="text-xs font-semibold text-zinc-300">
                  {m.role === "user" ? "You" : agentName(agents, m.agent_id)}
                </span>
                {m.role === "assistant" && m.agent_id && (
                  <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-indigo-400">
                    @{m.agent_id}
                  </span>
                )}
              </div>

              {m.role === "user" ? (
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-200">
                  {m.content}
                </p>
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
