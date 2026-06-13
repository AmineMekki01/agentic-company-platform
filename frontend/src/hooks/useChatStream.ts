import { useCallback, useRef, useState } from "react";

import { getToken } from "@/lib/api";

export interface SourceInfo {
  rank: number;
  title: string;
  id: string;
  url: string | null;
}

export interface StreamCallbacks {
  onAgent?: (agent: string) => void;
  onToken: (delta: string) => void;
  onSources?: (sources: SourceInfo[]) => void;
  onStep?: (step: string) => void;
  onTitle?: (title: string) => void;
  onDone?: (payload: { message_id: string; title: string | null }) => void;
  onError?: (detail: string) => void;
}

export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const send = useCallback(
    async (
      conversationId: string,
      content: string,
      agent: string | null,
      forceAgent: boolean,
      mode: string,
      callbacks: StreamCallbacks
    ) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);

      try {
        const res = await fetch(`/api/chat/${conversationId}/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({ content, agent, force_agent: forceAgent, mode }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          let detail = `Request failed (${res.status})`;
          try {
            const body = await res.json();
            if (typeof body.detail === "string") detail = body.detail;
          } catch {
          }
          callbacks.onError?.(detail);
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() ?? "";

          for (const block of blocks) {
            let event = "message";
            let data = "";
            for (const line of block.split(/\r?\n/)) {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) data += line.slice(5).trim();
            }
            if (!data) continue;

            try {
              const payload = JSON.parse(data);
              if (event === "agent") callbacks.onAgent?.(payload.agent);
              else if (event === "token") callbacks.onToken(payload.delta);
              else if (event === "sources") callbacks.onSources?.(payload.sources);
              else if (event === "step") callbacks.onStep?.(payload.step);
              else if (event === "title") callbacks.onTitle?.(payload.title);
              else if (event === "done") {
                callbacks.onDone?.(payload);
                setStreaming(false);
              }
              else if (event === "error") callbacks.onError?.(payload.detail);
            } catch {
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          callbacks.onError?.("Connection lost while streaming.");
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    []
  );

  return { send, stop, streaming };
}
