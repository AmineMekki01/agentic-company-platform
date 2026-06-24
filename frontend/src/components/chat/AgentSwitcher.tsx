import { useEffect, useRef, useState } from "react";
import { Bot, Check, ChevronDown } from "lucide-react";

import type { Agent } from "@/lib/api";

interface AgentSwitcherProps {
  agents: Agent[];
  selected: string;
  onSelect: (slug: string) => void;
}

export default function AgentSwitcher({ agents, selected, onSelect }: AgentSwitcherProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const current = agents.find((a) => a.slug === selected);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-xl border border-line/80 bg-card px-3 py-1.5 text-sm font-medium transition-all hover:bg-hover hover:border-line"
      >
        <Bot className="h-4 w-4 text-brand" />
        <span className="truncate max-w-[200px]">{current?.name ?? selected}</span>
        <ChevronDown className={`h-3.5 w-3.5 text-tertiary transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="animate-scale-in absolute left-0 top-full z-10 mt-2 w-80 overflow-hidden rounded-2xl border border-line/80 bg-popover backdrop-blur-md shadow-2xl shadow-black/40">
          <div className="max-h-80 overflow-y-auto py-1">
            {agents.map((a) => (
              <button
                key={a.slug}
                onClick={() => {
                  onSelect(a.slug);
                  setOpen(false);
                }}
                className={`flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition ${
                  a.slug === selected ? "bg-brand/10" : "hover:bg-hover"
                }`}
              >
                <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                  a.slug === selected ? "bg-brand/15" : "bg-hover"
                }`}>
                  <Bot className={`h-3.5 w-3.5 ${a.slug === selected ? "text-brand" : "text-secondary"}`} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-medium ${a.slug === selected ? "text-brand" : "text-primary"}`}>
                    {a.name}
                    <span className="ml-1.5 text-xs text-tertiary">@{a.slug}</span>
                  </p>
                  <p className="truncate text-xs text-tertiary">{a.description}</p>
                </div>
                {a.slug === selected && (
                  <Check className="mt-1 h-4 w-4 shrink-0 text-brand" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
