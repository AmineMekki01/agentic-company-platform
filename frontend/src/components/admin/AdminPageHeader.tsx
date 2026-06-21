import type { LucideIcon } from "lucide-react";

interface AdminPageHeaderProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  iconColor?: string;
  iconBg?: string;
  children?: React.ReactNode;
}

export default function AdminPageHeader({
  title,
  description,
  icon: Icon,
  iconColor = "text-indigo-400",
  iconBg = "bg-indigo-500/10",
  children,
}: AdminPageHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-8">
      <div className="flex items-start gap-3.5">
        {Icon && (
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${iconBg} ring-1 ring-white/5`}>
            <Icon className={`h-5 w-5 ${iconColor}`} />
          </div>
        )}
        <div className="min-w-0 pt-0.5">
          <h1 className="text-xl font-semibold tracking-tight text-white">{title}</h1>
          {description && (
            <p className="text-sm text-zinc-500 mt-1">{description}</p>
          )}
        </div>
      </div>
      {children && <div className="flex items-center gap-2 shrink-0 pt-1">{children}</div>}
    </div>
  );
}
