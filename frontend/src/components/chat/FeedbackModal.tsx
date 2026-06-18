import { useState } from "react";
import { ThumbsUp, ThumbsDown, X, ImageIcon } from "lucide-react";
import { api } from "@/lib/api";

interface FeedbackModalProps {
  conversationId: string;
  messageId: string;
  initialThumbsUp: boolean;
  onClose: () => void;
  onSubmitted: () => void;
}

export default function FeedbackModal({
  conversationId,
  messageId,
  initialThumbsUp,
  onClose,
  onSubmitted,
}: FeedbackModalProps) {
  const [thumbsUp, setThumbsUp] = useState(initialThumbsUp);
  const [comment, setComment] = useState("");
  const [screenshotPreview, setScreenshotPreview] = useState<string | null>(null);
  const [screenshotAttachmentId, setScreenshotAttachmentId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [uploadingScreenshot, setUploadingScreenshot] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScreenshotChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setError("Only image files are allowed");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("Image must be under 10MB");
      return;
    }
    setError(null);

    // Preview
    const reader = new FileReader();
    reader.onloadend = () => setScreenshotPreview(reader.result as string);
    reader.readAsDataURL(file);

    // Upload immediately
    setUploadingScreenshot(true);
    try {
      const attachment = await api.uploadFeedbackScreenshot(file);
      setScreenshotAttachmentId(attachment.id);
    } catch (err) {
      setError("Failed to upload screenshot");
      setScreenshotPreview(null);
    } finally {
      setUploadingScreenshot(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.submitMessageFeedback(conversationId, messageId, {
        thumbs_up: thumbsUp,
        comment: comment.trim() || null,
        screenshot_attachment_id: screenshotAttachmentId,
      });
      onSubmitted();
      onClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to submit feedback";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-zinc-700 bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-zinc-100">Rate this response</h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Thumbs toggle */}
        <div className="mb-4 flex gap-3">
          <button
            onClick={() => setThumbsUp(true)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-3 transition ${
              thumbsUp
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : "border-zinc-700 bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800"
            }`}
          >
            <ThumbsUp className="h-5 w-5" />
            <span className="text-sm font-medium">Helpful</span>
          </button>
          <button
            onClick={() => setThumbsUp(false)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-3 transition ${
              !thumbsUp
                ? "border-rose-500/40 bg-rose-500/10 text-rose-400"
                : "border-zinc-700 bg-zinc-800/50 text-zinc-400 hover:bg-zinc-800"
            }`}
          >
            <ThumbsDown className="h-5 w-5" />
            <span className="text-sm font-medium">Not helpful</span>
          </button>
        </div>

        {/* Comment */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-zinc-400">
            Comment (optional)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What was good or what could be improved?"
            className="w-full rounded-xl border border-zinc-700 bg-zinc-800/50 px-3 py-2.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/20"
            rows={3}
          />
        </div>

        {/* Screenshot */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-zinc-400">
            Screenshot (optional)
          </label>
          {screenshotPreview ? (
            <div className="relative rounded-xl border border-zinc-700 bg-zinc-800/50 p-2">
              <img
                src={screenshotPreview}
                alt="Screenshot preview"
                className="max-h-40 w-full rounded-lg object-contain"
              />
              <button
                onClick={() => {
                  setScreenshotPreview(null);
                  setScreenshotAttachmentId(null);
                }}
                className="absolute right-3 top-3 rounded-full bg-zinc-900/80 p-1 text-zinc-400 hover:text-zinc-200"
              >
                <X className="h-4 w-4" />
              </button>
              {uploadingScreenshot && (
                <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-black/40">
                  <span className="text-sm text-white">Uploading…</span>
                </div>
              )}
            </div>
          ) : (
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-zinc-700 bg-zinc-800/30 px-4 py-6 transition hover:bg-zinc-800/50">
              <ImageIcon className="h-5 w-5 text-zinc-500" />
              <span className="text-sm text-zinc-400">Click to upload screenshot</span>
              <input
                type="file"
                accept="image/*"
                onChange={handleScreenshotChange}
                className="hidden"
              />
            </label>
          )}
        </div>

        {error && (
          <div className="mb-3 rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-400">
            {error}
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-800/50 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || uploadingScreenshot}
            className="flex-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}
