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
        className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm font-medium transition hover:bg-zinc-800"
      >
        <Bot className="h-4 w-4 text-indigo-400" />
        {current?.name ?? selected}
        <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-10 mt-1.5 w-80 overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
          {agents.map((a) => (
            <button
              key={a.slug}
              onClick={() => {
                onSelect(a.slug);
                setOpen(false);
              }}
              className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition hover:bg-zinc-800"
            >
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600/20">
                <Bot className="h-3.5 w-3.5 text-indigo-400" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-zinc-200">
                  {a.name}
                  <span className="ml-1.5 text-xs text-zinc-500">@{a.slug}</span>
                </p>
                <p className="truncate text-xs text-zinc-500">{a.description}</p>
              </div>
              {a.slug === selected && (
                <Check className="mt-1 h-4 w-4 shrink-0 text-indigo-400" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
