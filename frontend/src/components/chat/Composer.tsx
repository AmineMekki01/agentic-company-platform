import { useEffect, useRef, useState } from "react";
import { AtSign, Paperclip, SendHorizonal, Square, X } from "lucide-react";

import type { Agent } from "@/lib/api";

interface ComposerProps {
  agents: Agent[];
  selectedAgent: string;
  disabled: boolean;
  streaming: boolean;
  focusKey: number;
  onSend: (content: string, agent: string | null, files: File[]) => void;
  onStop: () => void;
  awaitingClarification?: boolean;
  onClarificationResponse?: (answer: string) => void;
}

export default function Composer({
  agents,
  selectedAgent,
  disabled,
  streaming,
  focusKey,
  onSend,
  onStop,
  awaitingClarification,
  onClarificationResponse,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [forcedAgent, setForcedAgent] = useState<string | null>(null);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeAgentSlug = forcedAgent ?? selectedAgent;
  const activeAgent = agents.find((a) => a.slug === activeAgentSlug);
  const canUpload = activeAgent ? activeAgent.allow_uploads !== false : false;

  const suggestions =
    mentionQuery !== null
      ? agents.filter((a) =>
          a.slug.toLowerCase().startsWith(mentionQuery.toLowerCase())
        )
      : [];

  useEffect(() => {
    setHighlighted(0);
  }, [mentionQuery]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, [focusKey]);

  // Keyboard shortcut: '/' focuses composer
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (
        e.key === "/" &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        document.activeElement !== textareaRef.current &&
        document.activeElement?.tagName !== "INPUT"
      ) {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (!canUpload && files.length > 0) {
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [canUpload, files.length]);

  function detectMention(text: string, caret: number) {
    const upToCaret = text.slice(0, caret);
    const match = upToCaret.match(/(?:^|\s)@(\w*)$/);
    setMentionQuery(match ? match[1] : null);
  }

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value);
    detectMention(e.target.value, e.target.selectionStart);
  }

  function pickAgent(slug: string) {
    setForcedAgent(slug);
    setValue((v) => v.replace(/(^|\s)@\w*$/, "$1").trimEnd());
    setMentionQuery(null);
    textareaRef.current?.focus();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFiles((prev) => [...prev, file]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function submit() {
    const content = value.trim();
    const allowedFiles = canUpload ? files : [];
    if ((!content && allowedFiles.length === 0) || disabled) return;
    if (awaitingClarification && onClarificationResponse) {
      onClarificationResponse(content);
      setValue("");
      setFiles([]);
      setMentionQuery(null);
      return;
    }
    onSend(content, forcedAgent, allowedFiles);
    setValue("");
    setFiles([]);
    setMentionQuery(null);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (mentionQuery !== null && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlighted((h) => (h + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlighted((h) => (h - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        pickAgent(suggestions[highlighted].slug);
        return;
      }
      if (e.key === "Escape") {
        setMentionQuery(null);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-line bg-canvas px-4 py-4">
      <div className="relative mx-auto max-w-3xl">
        {mentionQuery !== null && suggestions.length > 0 && (
          <div className="absolute bottom-full left-0 mb-2 w-72 overflow-hidden rounded-xl border border-line bg-popover shadow-2xl">
            {suggestions.map((a, i) => (
              <button
                key={a.slug}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pickAgent(a.slug);
                }}
                onMouseEnter={() => setHighlighted(i)}
                className={`flex w-full items-start gap-2 px-3 py-2 text-left ${
                  i === highlighted ? "bg-hover" : ""
                }`}
              >
                <AtSign className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
                <span>
                  <span className="block text-sm font-medium text-primary">
                    {a.name}
                    <span className="ml-1.5 text-xs text-tertiary">@{a.slug}</span>
                  </span>
                  <span className="block truncate text-xs text-tertiary">
                    {a.description}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="rounded-2xl border border-line/80 bg-card shadow-sm backdrop-blur-sm transition focus-within:border-brand/50 focus-within:ring-2 focus-within:ring-brand/10">
          {forcedAgent && (
            <div className="flex items-center gap-1 px-3 pt-2.5">
              <span className="flex items-center gap-1 rounded-md bg-brand/20 px-2 py-0.5 text-xs font-medium text-brand">
                <AtSign className="h-3 w-3" />
                {forcedAgent}
                <button
                  onClick={() => setForcedAgent(null)}
                  className="ml-0.5 text-brand hover:text-brand-hover"
                  aria-label="Clear forced agent"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            </div>
          )}

          {canUpload && files.length > 0 && (
            <div className="flex flex-wrap gap-2 px-3 pt-2.5">
              {files.map((file, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line bg-hover px-2 py-0.5 text-xs text-secondary"
                >
                  <Paperclip className="h-3 w-3 text-tertiary" />
                  {file.name}
                  <button
                    onClick={() => removeFile(i)}
                    className="ml-0.5 text-tertiary hover:text-secondary"
                    aria-label="Remove file"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="flex items-end gap-2 px-3 py-2.5">
            {canUpload && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-secondary transition hover:bg-hover hover:text-primary disabled:opacity-40"
                  aria-label="Attach file"
                  title="Attach file"
                >
                  <Paperclip className="h-4 w-4" />
                </button>
              </>
            )}

            <textarea
              ref={textareaRef}
              rows={1}
              value={value}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder={awaitingClarification ? "Answer the question and press Enter to continue research…" : "Message… (use @ to call a specific agent)"}
              className="max-h-40 min-h-[24px] flex-1 resize-none bg-transparent text-sm leading-6 outline-none placeholder:text-tertiary"
              style={{ height: "auto" }}
              onInput={(e) => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = `${Math.min(t.scrollHeight, 160)}px`;
              }}
            />
            {streaming ? (
              <button
                onClick={onStop}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-hover text-primary transition hover:bg-tertiary active:scale-95"
                aria-label="Stop streaming"
              >
                <Square className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                onClick={submit}
                disabled={disabled || (!value.trim() && !awaitingClarification)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-white shadow-lg transition-all active:scale-95 disabled:opacity-40 disabled:active:scale-100 disabled:shadow-none ${
                  awaitingClarification
                    ? "bg-gradient-to-br from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20"
                    : "bg-gradient-to-br from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 shadow-indigo-500/20"
                }`}
                aria-label={awaitingClarification ? "Send clarification answer" : "Send message"}
              >
                <SendHorizonal className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        <div className="mt-2 flex items-center justify-between px-1">
          <p className="text-[11px] text-tertiary">
            Press <kbd className="rounded-md border border-line bg-card px-1.5 py-0.5 font-mono text-[10px] text-tertiary">/</kbd> to focus · <kbd className="rounded-md border border-line bg-card px-1.5 py-0.5 font-mono text-[10px] text-tertiary">Enter</kbd> to send
          </p>
          <span className={`text-[11px] font-mono tabular-nums transition ${
            value.length > 3000 ? "text-warning" : "text-tertiary"
          }`}>
            {value.length.toLocaleString()}
          </span>
        </div>
        <p className="mt-1 text-center text-[11px] text-tertiary">
          Agents can make mistakes. Verify important company information.
        </p>
      </div>
    </div>
  );
}
