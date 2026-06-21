import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";

import AgentSwitcher from "@/components/chat/AgentSwitcher";
import Composer from "@/components/chat/Composer";
import JiraTicketButton from "@/components/chat/JiraTicketButton";
import MessageList, { type DisplayMessage } from "@/components/chat/MessageList";
import ModeSelector, { type Mode } from "@/components/chat/ModeSelector";
import Sidebar from "@/components/chat/Sidebar";
import { useChatStream, type SourceInfo } from "@/hooks/useChatStream";
import { api, type Agent, type Conversation, type ConversationFolder } from "@/lib/api";
import { useAuth } from "@/stores/auth";

export default function ChatPage() {
  const { conversationId: urlConversationId } = useParams();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [folders, setFolders] = useState<ConversationFolder[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [focusKey, setFocusKey] = useState(0);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [testDraft, setTestDraft] = useState(false);
  const [feedbackMap, setFeedbackMap] = useState<Record<string, { thumbs_up: boolean }>>({});
  const { send, stop, streaming } = useChatStream();
  const { isAdmin } = useAuth();
  const didAutoOpen = useRef(false);

  const loadFolders = useCallback(async () => {
    try {
      const data = await api.listConversationFolders();
      setFolders(data);
    } catch {
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await api.listConversations();
      setConversations(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadConversations();
    loadFolders();
    api.listAgents()
      .then((loaded) => {
        setAgents(loaded);
        if (loaded.length && !selectedAgent) {
          const router = loaded.find((a) => a.slug.includes("general") || a.name?.toLowerCase().includes("router"));
          const entry = router ? router.slug : loaded[0].slug;
          setSelectedAgent(entry);
        }
      })
      .catch(() => {})
      .finally(() => setHasLoaded(true));
  }, [loadConversations, loadFolders]);

  // Update URL when active conversation changes
  useEffect(() => {
    if (activeId) {
      navigate(`/${activeId}`, { replace: true });
    } else {
      navigate("/", { replace: true });
    }
  }, [activeId, navigate]);

  const openConversation = useCallback(async (id: string) => {
    setActiveId(id);
    setFocusKey((k) => k + 1);
    setMessages([]);
    setFeedbackMap({});
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

  // Auto-open conversation from URL param once on initial load
  useEffect(() => {
    if (didAutoOpen.current) return;
    if (urlConversationId && conversations.length) {
      const exists = conversations.some((c) => c.id === urlConversationId);
      if (exists) {
        didAutoOpen.current = true;
        openConversation(urlConversationId);
      }
    }
  }, [urlConversationId, conversations, openConversation]);

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

  async function handleCreateFolder(name: string, color: string | null) {
    const folder = await api.createConversationFolder({ name, color });
    setFolders((fs) => [...fs, folder]);
  }

  async function handleDeleteFolder(id: string) {
    await api.deleteConversationFolder(id);
    setFolders((fs) => fs.filter((f) => f.id !== id));
    setConversations((cs) =>
      cs.map((c) => (c.folder_id === id ? { ...c, folder_id: null } : c))
    );
  }

  async function handleMoveConversation(conversationId: string, folderId: string | null) {
    const updated = await api.moveConversationToFolder(conversationId, folderId);
    setConversations((cs) =>
      cs.map((c) => (c.id === conversationId ? updated : c))
    );
  }

  async function handleSend(content: string, forcedAgent: string | null, files: File[] = []) {
    let conversationId = activeId;
    if (!conversationId) {
      const created = await api.createConversation();
      conversationId = created.id;
      setActiveId(created.id);
      setConversations((cs) => [created, ...cs]);
    }

    const activeAgentSlug = forcedAgent ?? selectedAgent;
    const canUpload = agents.find((a) => a.slug === activeAgentSlug)?.allow_uploads !== false;

    const attachmentIds: string[] = [];
    const uploadedAttachments: { filename: string; extractedText: string | null }[] = [];
    for (const file of canUpload ? files : []) {
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
      { id: placeholderId, role: "assistant", content: "", agent_id: agent, streaming: true, step: "routing", draft: testDraft },
    ]);

    await send(conversationId, content.trim(), agent, isForced, mode, {
      onAgent: (slug) => {
        setMessages((ms) =>
          ms.map((m) => (m.id === placeholderId ? { ...m, agent_id: slug } : m))
        );
      },
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
            m.id === placeholderId ? { ...m, serverId: message_id, streaming: false, step: undefined } : m
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
    }, attachmentIds, testDraft);
  }

  if (!hasLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="flex flex-col items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
          </div>
          <p className="text-sm text-zinc-500">Loading…</p>
        </div>
      </div>
    );
  }

  const noAgents = agents.length === 0;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        folders={folders}
        activeId={activeId}
        onSelect={openConversation}
        onNew={newChat}
        onDelete={handleDelete}
        onCreateFolder={handleCreateFolder}
        onDeleteFolder={handleDeleteFolder}
        onMoveConversation={handleMoveConversation}
      />

      <main className="flex min-w-0 flex-1 flex-col bg-zinc-900/50">
        {noAgents ? (
          <div className="flex flex-1 items-center justify-center px-4 text-center">
            <div>
              <h1 className="text-xl font-semibold text-zinc-200">No access</h1>
              <p className="mt-2 max-w-sm text-sm text-zinc-500">
                You do not have access to any agents. Contact an administrator if you think this is a mistake.
              </p>
            </div>
          </div>
        ) : (
          <>
            <header className="flex items-center justify-between border-b border-zinc-800/60 bg-zinc-950/80 px-4 py-2.5 backdrop-blur-sm z-10">
              {/* Left: Agent + Mode */}
              <div className="flex items-center gap-2.5 min-w-0 flex-1">
                <AgentSwitcher
                  agents={agents}
                  selected={selectedAgent}
                  onSelect={(slug) => {
                    if (slug !== selectedAgent) {
                      setSelectedAgent(slug);
                      setTestDraft(false);
                      newChat();
                    }
                  }}
                />
                <div className="h-4 w-px bg-zinc-800" />
                <ModeSelector selected={mode} onSelect={setMode} />
              </div>

              {/* Center: Conversation title */}
              <div className="flex-1 flex justify-center min-w-0 px-4">
                <div className="flex items-center gap-2 max-w-md">
                  <div className={`h-1.5 w-1.5 rounded-full ${activeId ? "bg-emerald-400" : "bg-zinc-600"}`} />
                  <h1 className="truncate text-sm font-medium text-zinc-300">
                    {activeId
                      ? (conversations.find((c) => c.id === activeId)?.title ?? "Untitled conversation")
                      : "New chat"}
                  </h1>
                </div>
              </div>

              {/* Right: Admin controls + Streaming */}
              <div className="flex items-center gap-3 flex-1 justify-end min-w-0">
                {isAdmin() && (
                  <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none shrink-0 rounded-lg border border-zinc-800 bg-zinc-900/60 px-2.5 py-1.5 transition hover:border-zinc-700 hover:text-zinc-300">
                    <input
                      type="checkbox"
                      checked={testDraft}
                      onChange={(e) => setTestDraft(e.target.checked)}
                      className="accent-indigo-500 h-3.5 w-3.5"
                    />
                    <span>Test Draft</span>
                  </label>
                )}
                {streaming && (
                  <div className="flex items-center gap-2 rounded-full bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 shrink-0">
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
                    </span>
                    <span className="text-xs font-medium text-indigo-300">Agent is responding…</span>
                  </div>
                )}
              </div>
            </header>

            <MessageList
              messages={messages}
              agents={agents}
              conversationId={activeId ?? undefined}
              feedbackMap={feedbackMap}
              onFeedbackSubmitted={(messageId, thumbsUp) => {
                setFeedbackMap((prev) => ({ ...prev, [messageId]: { thumbs_up: thumbsUp } }));
              }}
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
                <div className="animate-fade-in-up flex flex-col items-center justify-center h-full px-4">
                  <div className="relative mb-6">
                    <div className="absolute inset-0 bg-indigo-500/20 rounded-3xl blur-xl" />
                    <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 ring-1 ring-white/10">
                      <Sparkles className="h-8 w-8 text-indigo-400" />
                    </div>
                  </div>
                  <h2 className="text-lg font-semibold text-white">How can I help you today?</h2>
                  <p className="mt-2 max-w-sm text-sm text-zinc-500 text-center leading-relaxed">
                    Ask anything, or use <span className="font-mono text-indigo-400 bg-indigo-500/10 px-1 py-0.5 rounded">@agent-name</span> to call
                    a specific agent directly.
                  </p>

                  {/* Quick suggestion chips */}
                  <div className="mt-8 flex flex-wrap justify-center gap-2 max-w-md">
                    {["What is our expense policy?", "Create a Jira ticket for...", "Summarize last quarter", "@finance check budget"].map((s) => (
                      <button
                        key={s}
                        onClick={() => {
                          const composer = document.querySelector("textarea[placeholder]") as HTMLTextAreaElement | null;
                          if (composer) {
                            composer.value = s;
                            composer.dispatchEvent(new Event("input", { bubbles: true }));
                            composer.focus();
                          }
                        }}
                        className="rounded-full border border-zinc-800 bg-zinc-900/60 px-3.5 py-1.5 text-xs text-zinc-400 transition hover:border-zinc-700 hover:text-zinc-300 hover:bg-zinc-800/60"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              }
            />

            <Composer
              agents={agents}
              selectedAgent={selectedAgent}
              disabled={streaming}
              streaming={streaming}
              focusKey={focusKey}
              onSend={handleSend}
              onStop={stop}
            />
          </>
        )}
      </main>
    </div>
  );
}
