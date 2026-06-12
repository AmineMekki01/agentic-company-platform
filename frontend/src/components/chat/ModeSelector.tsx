import { useEffect, useRef, useState } from "react";
import { Bolt, Brain, ChevronDown, Layers, Zap } from "lucide-react";

export type Mode = "auto" | "quick" | "mid" | "deep";

interface ModeOption {
  value: Mode;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const MODES: ModeOption[] = [
  {
    value: "auto",
    label: "Auto",
    description: "Adaptive depth based on query complexity",
    icon: <Zap className="h-3.5 w-3.5 text-emerald-400" />,
  },
  {
    value: "quick",
    label: "Quick",
    description: "Fast response, brief search only",
    icon: <Bolt className="h-3.5 w-3.5 text-amber-400" />,
  },
  {
    value: "mid",
    label: "Mid",
    description: "Balanced depth, standard search",
    icon: <Layers className="h-3.5 w-3.5 text-sky-400" />,
  },
  {
    value: "deep",
    label: "Deep",
    description: "Deep analysis, multi-search if needed",
    icon: <Brain className="h-3.5 w-3.5 text-indigo-400" />,
  },
];

interface ModeSelectorProps {
  selected: Mode;
  onSelect: (mode: Mode) => void;
}

export default function ModeSelector({ selected, onSelect }: ModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const current = MODES.find((m) => m.value === selected) ?? MODES[0];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-zinc-300 transition hover:bg-zinc-800"
      >
        {current.icon}
        {current.label}
        <ChevronDown className="h-3 w-3 text-zinc-500" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-1.5 w-60 overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => {
                onSelect(m.value);
                setOpen(false);
              }}
              className={`flex w-full items-start gap-2.5 px-3 py-2.5 text-left transition hover:bg-zinc-800 ${
                m.value === selected ? "bg-zinc-800/60" : ""
              }`}
            >
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-zinc-800">
                {m.icon}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-zinc-200">{m.label}</p>
                <p className="truncate text-[11px] text-zinc-500">{m.description}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
