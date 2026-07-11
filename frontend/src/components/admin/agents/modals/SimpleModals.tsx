import { ExternalLink, Loader2, Rocket, Trash2 } from "lucide-react";

interface DeleteConfirmProps {
  slug: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteConfirmModal({ slug, onCancel, onConfirm }: DeleteConfirmProps) {
  return (
    <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="animate-scale-in bg-canvas border border-line rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-danger-soft">
            <Trash2 className="h-5 w-5 text-danger" />
          </div>
          <h2 className="font-semibold text-lg">Delete Agent?</h2>
        </div>
        <p className="text-sm text-secondary">
          Are you sure you want to delete <strong className="text-primary">{slug}</strong>? This cannot be undone.
        </p>
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm bg-card hover:bg-hover border border-line/60 transition"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="bg-danger hover:bg-danger-hover px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-danger/15"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

interface PublishModalProps {
  isPublished: boolean;
  publishNotes: string;
  setPublishNotes: (v: string) => void;
  publishing: boolean;
  onCancel: () => void;
  onPublish: () => void;
}

export function PublishModal({ isPublished, publishNotes, setPublishNotes, publishing, onCancel, onPublish }: PublishModalProps) {
  return (
    <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="animate-scale-in bg-canvas border border-line rounded-2xl p-6 w-full max-w-sm space-y-4 shadow-2xl">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand/10">
            <Rocket className="h-5 w-5 text-brand" />
          </div>
          <div>
            <h2 className="font-semibold text-lg">
              {isPublished ? "Publish Changes" : "Publish Agent"}
            </h2>
            <p className="text-xs text-tertiary">
              {isPublished
                ? "This will snapshot the current live config and apply your draft changes."
                : "This will make the agent visible to all permitted users."}
            </p>
          </div>
        </div>

        <label className="block">
          <span className="text-xs font-medium text-secondary">Notes (optional)</span>
          <textarea
            value={publishNotes}
            onChange={(e) => setPublishNotes(e.target.value)}
            placeholder="What changed in this version?"
            rows={2}
            className="w-full bg-card border border-line/60 rounded-xl px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
          />
        </label>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm bg-card hover:bg-hover border border-line/60 transition"
          >
            Cancel
          </button>
          <button
            onClick={onPublish}
            disabled={publishing}
            className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-4 py-2 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-brand/15"
          >
            {publishing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
            {publishing ? "Publishing…" : "Publish"}
          </button>
        </div>
      </div>
    </div>
  );
}

interface TestDraftModalProps {
  testDraftMessage: string;
  setTestDraftMessage: (v: string) => void;
  testDraftResponse: string;
  testDraftTraceUrl?: string | null;
  testingDraft: boolean;
  onCancel: () => void;
  onSend: () => void;
}

export function TestDraftModal({ testDraftMessage, setTestDraftMessage, testDraftResponse, testDraftTraceUrl, testingDraft, onCancel, onSend }: TestDraftModalProps) {
  return (
    <div className="animate-fade-in fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-canvas border border-line rounded-2xl p-6 w-full max-w-lg space-y-4 shadow-2xl flex flex-col max-h-[80vh]">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-lg">Test Draft</h2>
            <p className="text-xs text-tertiary">
              Runs the full agent graph with your draft config — including tools, retrieval, routing, and orchestration.
            </p>
          </div>
          <button onClick={onCancel} className="text-tertiary hover:text-secondary transition">✕</button>
        </div>

        <div className="space-y-2 flex-1 overflow-y-auto">
          <label className="block">
            <span className="text-xs font-medium text-secondary">Your message</span>
            <textarea
              value={testDraftMessage}
              onChange={(e) => setTestDraftMessage(e.target.value)}
              placeholder="Type a test message..."
              rows={3}
              className="w-full bg-card border border-line/60 rounded-xl px-3 py-2 text-sm mt-1 text-primary placeholder:text-tertiary focus:border-brand/50 focus:ring-2 focus:ring-brand/10 outline-none transition resize-y"
            />
          </label>

          <div className="flex justify-end">
            <button
              onClick={onSend}
              disabled={testingDraft || !testDraftMessage.trim()}
              className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-3 py-2 rounded-lg text-sm font-medium text-white transition"
            >
              {testingDraft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />}
              {testingDraft ? "Testing…" : "Send"}
            </button>
          </div>

          {testDraftResponse && (
            <div className="mt-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-secondary">Response</span>
                {testDraftTraceUrl && (
                  <a
                    href={testDraftTraceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[11px] text-brand hover:underline"
                    title="View full trace in Langfuse"
                  >
                    <ExternalLink className="h-3 w-3" />
                    Trace
                  </a>
                )}
              </div>
              <div className="mt-1 bg-card border border-line/60 rounded-xl px-3 py-2 text-sm text-secondary whitespace-pre-wrap max-h-64 overflow-y-auto">
                {testDraftResponse}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
