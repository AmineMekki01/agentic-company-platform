import { useState } from "react";
import { Ticket, Loader2 } from "lucide-react";
import type { JiraTicketDraft } from "@/lib/api";
import { api } from "@/lib/api";
import TicketDraftCard from "./TicketDraftCard";

interface JiraTicketButtonProps {
  conversationId: string;
}

export default function JiraTicketButton({ conversationId }: JiraTicketButtonProps) {
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState<JiraTicketDraft | null>(null);
  const [error, setError] = useState("");

  const handleGenerateDraft = async () => {
    setLoading(true);
    setError("");
    try {
      const d = await api.generateJiraDraft(conversationId);
      setDraft(d);
    } catch (err: any) {
      setError(err?.message || "Failed to generate draft");
    } finally {
      setLoading(false);
    }
  };

  const handleDecline = () => {
    setDraft(null);
    setError("");
  };

  if (draft) {
    return (
      <TicketDraftCard
        conversationId={conversationId}
        draft={draft}
        onDecline={handleDecline}
      />
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleGenerateDraft}
        disabled={loading}
        className="flex items-center gap-1.5 bg-brand/90 hover:bg-brand-hover disabled:opacity-50 px-3 py-1.5 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-brand/10"
      >
        {loading ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Generating...
          </>
        ) : (
          <>
            <Ticket className="h-3.5 w-3.5" />
            Create Jira Ticket
          </>
        )}
      </button>
      {error && <span className="text-danger text-xs bg-danger-soft border border-danger/20 rounded-md px-2 py-1">{error}</span>}
    </div>
  );
}
