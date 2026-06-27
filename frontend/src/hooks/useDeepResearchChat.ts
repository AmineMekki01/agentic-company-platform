import { useCallback, useRef, useState } from "react";

import { getToken } from "@/lib/api";

export interface DeepResearchStep {
  step: string;
  detail: string;
}

export interface DeepResearchCallbacks {
  onStep?: (step: DeepResearchStep) => void;
  onClarification?: (question: string, messageId?: string) => void;
  onToken: (delta: string) => void;
  onSources?: (sources: any[]) => void;
  onDone?: (messageId: string) => void;
  onError?: (detail: string) => void;
  onBudgetWarning?: (message: string) => void;
}

export function useDeepResearchChat() {
  const [streaming, setStreaming] = useState(false);
  const [clarification, setClarification] = useState<string | null>(null);
  const [steps, setSteps] = useState<DeepResearchStep[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const callbacksRef = useRef<DeepResearchCallbacks | null>(null);

  const stop = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStreaming(false);
    setClarification(null);
  }, []);

  const send = useCallback(
    async (conversationId: string, content: string, agent: string, _mode: string, callbacks: DeepResearchCallbacks) => {
      setStreaming(true);
      setClarification(null);
      setSteps([]);
      callbacksRef.current = callbacks;

      const token = getToken();
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/api/ws/chat/${conversationId}?token=${token}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const type = data.type;
          console.log('[DR] WS received:', type, data);
          const cb = callbacksRef.current ?? callbacks;

          if (type === "step") {
            const stepInfo = { step: data.step, detail: data.detail || "" };
            setSteps((prev) => [...prev, stepInfo]);
            cb.onStep?.(stepInfo);
          } else if (type === "clarification") {
            setClarification(data.question);
            cb.onClarification?.(data.question, data.message_id);
          } else if (type === "sources") {
            cb.onSources?.(data.sources || []);
          } else if (type === "token") {
            cb.onToken(data.delta || "");
          } else if (type === "done") {
            setStreaming(false);
            cb.onDone?.(data.message_id || "");
            ws.close();
            wsRef.current = null;
          } else if (type === "budget_warning") {
            cb.onBudgetWarning?.(data.message || "");
          } else if (type === "error") {
            setStreaming(false);
            cb.onError?.(data.detail || "Unknown error");
            ws.close();
            wsRef.current = null;
          }
        } catch {
        }
      };

      ws.onerror = () => {
        setStreaming(false);
        (callbacksRef.current ?? callbacks).onError?.("WebSocket connection error");
        wsRef.current = null;
      };

      ws.onclose = (event) => {
        console.log('[DR] WebSocket closed:', event.code, event.reason);
        setStreaming(false);
        wsRef.current = null;
      };

      ws.onopen = () => {
        console.log('[DR] WebSocket connected, sending message');
        ws.send(JSON.stringify({
          type: "message",
          content,
          agent,
          mode: _mode,
        }));
      };
    },
    [],
  );

  const sendClarificationResponse = useCallback(
    async (answer: string, agent: string, callbacks?: DeepResearchCallbacks) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      setClarification(null);
      setSteps([]);
      setStreaming(true);

      if (callbacks) {
        callbacksRef.current = callbacks;
      }

      ws.send(JSON.stringify({
        type: "clarification_response",
        content: answer,
        agent,
      }));
    },
    [],
  );

  return {
    send,
    stop,
    sendClarificationResponse,
    streaming,
    clarification,
    steps,
  };
}
