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
      className={`rounded-2xl border border-line/60 bg-card shadow-sm backdrop-blur-sm transition hover:border-line ${pad} ${className}`}
    >
      {(title || icon) && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            {icon && <span className="text-tertiary">{icon}</span>}
            {title && <h2 className="text-sm font-semibold text-primary">{title}</h2>}
          </div>
          {description && (
            <p className="text-xs text-tertiary">{description}</p>
          )}
        </div>
      )}
      {children}
    </div>
  );
}
