import type { ReactNode } from "react";

interface AdminCardProps {
  title?: string;
  description?: string;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg";
}

export default function AdminCard({
  title,
  description,
  icon,
  children,
  className = "",
  padding = "md",
}: AdminCardProps) {
  const pad = padding === "sm" ? "p-4" : padding === "md" ? "p-5" : "p-6";

  return (
    <div
      className={`rounded-2xl border border-zinc-800/60 bg-zinc-900/40 shadow-sm backdrop-blur-sm transition hover:border-zinc-700/60 ${pad} ${className}`}
    >
      {(title || icon) && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            {icon && <span className="text-zinc-500">{icon}</span>}
            {title && <h2 className="text-sm font-semibold text-zinc-200">{title}</h2>}
          </div>
          {description && (
            <p className="text-xs text-zinc-500">{description}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
