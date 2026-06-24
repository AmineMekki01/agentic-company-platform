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
    <div className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="animate-scale-in w-full max-w-md rounded-2xl border border-line/80 bg-card p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-primary">Rate this response</h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-tertiary hover:bg-hover hover:text-secondary"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Thumbs toggle */}
        <div className="mb-4 flex gap-3">
          <button
            onClick={() => setThumbsUp(true)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl border-2 px-4 py-3 transition ${
              thumbsUp
                ? "border-success bg-success-soft text-success"
                : "border-line bg-card text-secondary hover:bg-hover hover:border-line"
            }`}
          >
            <ThumbsUp className="h-5 w-5" />
            <span className="text-sm font-medium">Helpful</span>
          </button>
          <button
            onClick={() => setThumbsUp(false)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-xl border-2 px-4 py-3 transition ${
              !thumbsUp
                ? "border-danger bg-danger-soft text-danger"
                : "border-line bg-card text-secondary hover:bg-hover hover:border-line"
            }`}
          >
            <ThumbsDown className="h-5 w-5" />
            <span className="text-sm font-medium">Not helpful</span>
          </button>
        </div>

        {/* Comment */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-secondary">
            Comment (optional)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What was good or what could be improved?"
            className="w-full rounded-xl border border-line bg-hover/70 px-3 py-2.5 text-sm text-primary placeholder:text-tertiary focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand/20"
            rows={3}
          />
        </div>

        {/* Screenshot */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-secondary">
            Screenshot (optional)
          </label>
          {screenshotPreview ? (
            <div className="relative rounded-xl border border-line bg-hover/70 p-2">
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
                className="absolute right-3 top-3 rounded-full bg-canvas p-1 text-secondary hover:text-primary"
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
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-line bg-hover/70 px-4 py-6 transition hover:bg-hover/70">
              <ImageIcon className="h-5 w-5 text-tertiary" />
              <span className="text-sm text-secondary">Click to upload screenshot</span>
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
          <div className="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 rounded-xl border border-line bg-hover/70 px-4 py-2.5 text-sm font-medium text-secondary transition hover:bg-hover"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || uploadingScreenshot}
            className="flex-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-hover disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}
