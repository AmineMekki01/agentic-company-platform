import { useState } from "react";
import { Ticket, ExternalLink, Loader2 } from "lucide-react";
import type { JiraTicketDraft, JiraTicket } from "@/lib/api";
import { api } from "@/lib/api";

interface TicketDraftCardProps {
  conversationId: string;
  draft: JiraTicketDraft;
  onCreated?: (ticket: JiraTicket) => void;
  onDecline?: () => void;
}

export default function TicketDraftCard({
  conversationId,
  draft,
  onCreated,
  onDecline,
}: TicketDraftCardProps) {
  const [summary, setSummary] = useState(draft.summary);
  const [description, setDescription] = useState(draft.description);
  const [projectKey, setProjectKey] = useState(draft.project_key || "");
  const [issueType, setIssueType] = useState(draft.issue_type);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<JiraTicket | null>(null);
  const [error, setError] = useState("");

  const handleCreate = async () => {
    setCreating(true);
    setError("");
    try {
      const ticket = await api.createJiraTicket(conversationId, {
        summary,
        description,
        project_key: projectKey || null,
        issue_type: issueType,
      });
      setCreated(ticket);
      onCreated?.(ticket);
    } catch (err: any) {
      const msg = err?.detail || err?.message || "Failed to create ticket";
      setError(msg);
    } finally {
      setCreating(false);
    }
  };

  if (created) {
    return (
      <div className="rounded-xl border border-success/40 bg-success-soft p-4 max-w-lg">
        <div className="flex items-center gap-2 mb-2">
          <Ticket className="h-4 w-4 text-success" />
          <span className="font-medium text-success">Jira Ticket Created</span>
        </div>
        <p className="text-sm text-primary mb-2">
          <span className="font-semibold">{created.key}</span>: {created.summary}
        </p>
        <a
          href={created.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-brand hover:text-brand-hover"
        >
          Open in Jira <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-brand/40 bg-brand-soft p-4 max-w-lg">
      <div className="flex items-center gap-2 mb-3">
        <Ticket className="h-4 w-4 text-brand" />
        <span className="font-medium text-brand">Create Jira Ticket</span>
      </div>

      <div className="space-y-3">
        <div>
          <label className="text-xs text-secondary block mb-1">Summary</label>
          <input
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            className="w-full bg-canvas border border-line rounded-md px-3 py-2 text-sm text-primary"
          />
        </div>

        <div>
          <label className="text-xs text-secondary block mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full bg-canvas border border-line rounded-md px-3 py-2 text-sm text-primary resize-y"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-secondary block mb-1">Project Key</label>
            <input
              value={projectKey}
              onChange={(e) => setProjectKey(e.target.value)}
              placeholder="e.g. IT"
              className="w-full bg-canvas border border-line rounded-md px-3 py-2 text-sm text-primary"
            />
          </div>
          <div>
            <label className="text-xs text-secondary block mb-1">Issue Type</label>
            <select
              value={issueType}
              onChange={(e) => setIssueType(e.target.value)}
              className="w-full bg-canvas border border-line rounded-md px-3 py-2 text-sm text-primary"
            >
              <option value="Task">Task</option>
              <option value="Bug">Bug</option>
              <option value="Story">Story</option>
              <option value="Incident">Incident</option>
            </select>
          </div>
        </div>
      </div>

      {error && <p className="text-danger text-sm mt-2">{error}</p>}

      <div className="flex items-center gap-2 mt-4">
        <button
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-1.5 bg-brand hover:bg-brand-hover disabled:opacity-50 px-4 py-2 rounded-md text-sm font-medium text-white"
        >
          {creating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              <Ticket className="h-3.5 w-3.5" />
              Create Ticket
            </>
          )}
        </button>
        <button
          onClick={onDecline}
          disabled={creating}
          className="text-sm text-secondary hover:text-primary px-3 py-2"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
