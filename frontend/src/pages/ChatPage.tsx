import { useCallback, useEffect, useState } from "react";
import { Sparkles } from "lucide-react";

import AgentSwitcher from "@/components/chat/AgentSwitcher";
import Composer from "@/components/chat/Composer";
import JiraTicketButton from "@/components/chat/JiraTicketButton";
import MessageList, { type DisplayMessage } from "@/components/chat/MessageList";
import ModeSelector, { type Mode } from "@/components/chat/ModeSelector";
import Sidebar from "@/components/chat/Sidebar";
import { useChatStream, type SourceInfo } from "@/hooks/useChatStream";
import { api, type Agent, type Conversation } from "@/lib/api";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [focusKey, setFocusKey] = useState(0);
  const { send, stop, streaming } = useChatStream();

  useEffect(() => {
    api.listConversations().then(setConversations).catch(() => {});
    api.listAgents().then((loaded) => {
      setAgents(loaded);
      if (loaded.length && !selectedAgent) {
        const general = loaded.find((a) => a.slug === "general");
        setSelectedAgent(general ? general.slug : loaded[0].slug);
      }
    }).catch(() => {});
  }, []);

  const openConversation = useCallback(async (id: string) => {
    setActiveId(id);
    setFocusKey((k) => k + 1);
    setMessages([]);
    const detail = await api.getConversation(id);
    setActiveId((current) => {
      if (current === id) {
        setMessages(
          detail.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            agent_id: m.agent_id,
            sources: (m.citations as SourceInfo[] | undefined) ?? undefined,
            attachments: m.attachments?.map((att) => ({
              filename: att.filename,
              extractedText: att.extracted_text,
            })),
          }))
        );
        const lastAgentMsg = [...detail.messages]
          .reverse()
          .find((m) => m.role === "assistant" && m.agent_id);
        if (lastAgentMsg?.agent_id && agents.some((a) => a.slug === lastAgentMsg.agent_id)) {
          setSelectedAgent(lastAgentMsg.agent_id);
        } else if (agents.length) {
          setSelectedAgent(agents[0].slug);
        }
      }
      return current;
    });
  }, []);

  function newChat() {
    setActiveId(null);
    setMessages([]);
    setFocusKey((k) => k + 1);
  }

  async function handleDelete(id: string) {
    await api.deleteConversation(id);
    setConversations((cs) => cs.filter((c) => c.id !== id));
    if (id === activeId) newChat();
  }

  async function handleSend(content: string, forcedAgent: string | null, files: File[] = []) {
    let conversationId = activeId;
    if (!conversationId) {
      const created = await api.createConversation();
      conversationId = created.id;
      setActiveId(created.id);
      setConversations((cs) => [created, ...cs]);
    }

    const attachmentIds: string[] = [];
    const uploadedAttachments: { filename: string; extractedText: string | null }[] = [];
    for (const file of files) {
      try {
        const att = await api.uploadChatFile(conversationId, file);
        attachmentIds.push(att.id);
        uploadedAttachments.push({
          filename: att.filename,
          extractedText: att.extracted_text,
        });
      } catch (err: unknown) {
        const detail = err instanceof Error ? err.message : "Upload failed";
        uploadedAttachments.push({ filename: file.name, extractedText: null });
        console.warn("File upload failed:", detail);
      }
    }

    const agent = forcedAgent ?? selectedAgent;
    const isForced = !!forcedAgent;
    const userMsg: DisplayMessage = {
      id: `local-user-${Date.now()}`,
      role: "user",
      content: content.trim(),
      agent_id: null,
      attachments: uploadedAttachments.length > 0 ? uploadedAttachments : undefined,
    };
    const placeholderId = `local-assistant-${Date.now()}`;
    setMessages((ms) => [
      ...ms,
      userMsg,
      { id: placeholderId, role: "assistant", content: "", agent_id: agent, streaming: true, step: "routing" },
    ]);

    await send(conversationId, content.trim(), agent, isForced, mode, {
      onAgent: (slug) =>
        setMessages((ms) =>
          ms.map((m) => (m.id === placeholderId ? { ...m, agent_id: slug } : m))
        ),
      onToken: (delta) =>
        setMessages((ms) =>
          ms.map((m) =>
            m.id === placeholderId ? { ...m, content: m.content + delta } : m
          )
        ),
      onStep: (step) =>
        setMessages((ms) =>
          ms.map((m) =>
            m.id === placeholderId ? { ...m, step } : m
          )
        ),
      onSources: (sources) =>
        setMessages((ms) =>
          ms.map((m) =>
            m.id === placeholderId ? { ...m, sources } : m
          )
        ),
      onDone: ({ message_id, title }) => {
        setMessages((ms) =>
          ms.map((m) =>
            m.id === placeholderId ? { ...m, id: message_id, streaming: false, step: undefined } : m
          )
        );
        setConversations((cs) =>
          cs.map((c) =>
            c.id === conversationId && title ? { ...c, title } : c
          )
        );
      },
      onTitle: (title) =>
        setConversations((cs) =>
          cs.map((c) =>
            c.id === conversationId ? { ...c, title } : c
          )
        ),
      onError: (detail) =>
        setMessages((ms) =>
          ms.map((m) =>
            m.id === placeholderId
              ? { ...m, content: `⚠️ ${detail}`, streaming: false, step: undefined }
              : m
          )
        ),
    }, attachmentIds);
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onNew={newChat}
        onDelete={handleDelete}
      />

      <main className="flex min-w-0 flex-1 flex-col bg-zinc-900/50">
        <header className="flex items-center justify-between border-b border-zinc-800/60 bg-zinc-950/80 px-4 py-3 backdrop-blur-sm z-10">
          <div className="flex items-center gap-3">
            <AgentSwitcher
              agents={agents}
              selected={selectedAgent}
              onSelect={(slug) => {
                if (slug !== selectedAgent) {
                  setSelectedAgent(slug);
                  newChat();
                }
              }}
            />
            <ModeSelector selected={mode} onSelect={setMode} />
          </div>
          <div className="flex items-center gap-2">
            {streaming && (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
                </span>
                <span className="text-xs text-zinc-400">Agent is responding…</span>
              </>
            )}
          </div>
        </header>

        <MessageList
          messages={messages}
          agents={agents}
          renderAction={(msg) => {
            if (!activeId || msg.role !== "assistant" || msg.streaming || !msg.agent_id) {
              return null;
            }
            const agent = agents.find((a) => a.slug === msg.agent_id);
            if (!agent?.tools?.includes("create_jira_ticket")) {
              return null;
            }
            return <JiraTicketButton conversationId={activeId} />;
          }}
          emptyState={
            <div className="text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/20">
                <Sparkles className="h-6 w-6 text-indigo-400" />
              </div>
              <h2 className="text-lg font-semibold">How can I help you today?</h2>
              <p className="mt-1 max-w-sm text-sm text-zinc-500">
                Ask anything, or use <span className="text-indigo-400">@</span> to call
                a specific agent directly.
              </p>
            </div>
          }
        />

        <Composer
          agents={agents}
          disabled={streaming}
          streaming={streaming}
          focusKey={focusKey}
          onSend={handleSend}
          onStop={stop}
        />
      </main>
    </div>
  );
}
