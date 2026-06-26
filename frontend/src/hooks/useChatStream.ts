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
  onDone?: (payload: { message_id: string; title: string | null; user_message_id?: string }) => void;
  onError?: (detail: string) => void;
  onBudgetWarning?: (message: string) => void;
}

async function _parseSSEStream(
  res: Response,
  callbacks: StreamCallbacks,
  setStreaming: (v: boolean) => void,
) {
  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
    }
    callbacks.onError?.(detail);
    setStreaming(false);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
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
          console.log("[SSE] event=", event, "payload=", payload);
          if (event === "agent") callbacks.onAgent?.(payload.agent);
          else if (event === "token") {
            console.log("[SSE] token delta_len=", payload.delta?.length ?? 0, "delta_preview=", payload.delta?.substring(0, 100));
            callbacks.onToken(payload.delta);
          }
          else if (event === "sources") callbacks.onSources?.(payload.sources);
          else if (event === "step") callbacks.onStep?.(payload.step);
          else if (event === "title") callbacks.onTitle?.(payload.title);
          else if (event === "done") {
            callbacks.onDone?.(payload);
            setStreaming(false);
          }
          else if (event === "error") callbacks.onError?.(payload.detail);
          else if (event === "budget_warning") callbacks.onBudgetWarning?.(payload.message);
        } catch (e) {
          console.error("[SSE] JSON parse error:", e, "data=", data);
        }
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      callbacks.onError?.("Connection lost while streaming.");
    }
  } finally {
    setStreaming(false);
  }
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
      callbacks: StreamCallbacks,
      attachmentIds: string[] = [],
      draft: boolean = false
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
          body: JSON.stringify({
            content,
            agent,
            force_agent: forceAgent,
            mode,
            attachment_ids: attachmentIds,
            draft,
          }),
          signal: controller.signal,
        });

        await _parseSSEStream(res, callbacks, setStreaming);
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

  const regenerate = useCallback(
    async (
      conversationId: string,
      mode: string,
      callbacks: StreamCallbacks,
    ) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);

      try {
        const res = await fetch(`/api/chat/${conversationId}/regenerate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({ mode }),
          signal: controller.signal,
        });

        await _parseSSEStream(res, callbacks, setStreaming);
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

  const editMessage = useCallback(
    async (
      conversationId: string,
      messageId: string,
      content: string,
      mode: string,
      callbacks: StreamCallbacks,
    ) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);

      try {
        const res = await fetch(`/api/chat/${conversationId}/messages/${messageId}/edit`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getToken()}`,
          },
          body: JSON.stringify({ content, mode }),
          signal: controller.signal,
        });

        await _parseSSEStream(res, callbacks, setStreaming);
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

  return { send, stop, streaming, regenerate, editMessage };
}
