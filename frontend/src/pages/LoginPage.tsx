import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Loader2, Mail, Lock, AlertCircle } from "lucide-react";

import { useAuth } from "@/stores/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError((err as Error).message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 overflow-hidden bg-canvas">
      {/* Background gradient orbs */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-brand/10 rounded-full blur-[120px]" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-violet-500/10 rounded-full blur-[100px]" />

      {/* Subtle grid pattern */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="animate-fade-in-up relative w-full max-w-sm">
        {/* Logo header */}
        <div className="mb-8 flex flex-col items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-xl shadow-indigo-500/20 ring-1 ring-white/10">
            <Bot className="h-7 w-7 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-xl font-semibold tracking-tight text-primary">
              Agentic Company Platform
            </h1>
            <p className="mt-1 text-sm text-tertiary">Sign in to your workspace</p>
          </div>
        </div>

        {/* Card */}
        <form
          onSubmit={handleSubmit}
          className="space-y-5 rounded-2xl border border-line/80 bg-card p-6 shadow-2xl shadow-black/20 backdrop-blur-xl"
        >
          <div>
            <label className="mb-2 block text-xs font-medium text-secondary">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full rounded-xl border border-line bg-canvas pl-10 pr-3 py-2.5 text-sm text-primary outline-none placeholder:text-tertiary transition-all focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
            </div>
          </div>

          <div>
            <label className="mb-2 block text-xs font-medium text-secondary">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tertiary" />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-line bg-canvas pl-10 pr-3 py-2.5 text-sm text-primary outline-none placeholder:text-tertiary transition-all focus:border-brand/50 focus:ring-2 focus:ring-brand/10"
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl border border-danger-soft bg-danger-soft px-3 py-2.5 text-xs text-danger">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-3 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition-all hover:from-indigo-500 hover:to-violet-500 hover:shadow-indigo-500/30 active:scale-[0.98] disabled:opacity-50 disabled:active:scale-100"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-tertiary">
          Powered by Agentic AI Platform
        </p>
      </div>
    </div>
  );
}
