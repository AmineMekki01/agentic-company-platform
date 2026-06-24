import { create } from "zustand";

type Theme = "dark" | "light";

interface ThemeState {
  theme: Theme;
  toggle: () => void;
  setTheme: (t: Theme) => void;
}

function applyTheme(t: Theme) {
  const root = document.documentElement;
  root.classList.remove("dark", "light");
  root.classList.add(t);
  localStorage.setItem("theme", t);
}

const stored = (typeof localStorage !== "undefined" && localStorage.getItem("theme")) as Theme | null;
const initial: Theme = stored ?? "dark";
if (typeof document !== "undefined") applyTheme(initial);

export const useTheme = create<ThemeState>((set) => ({
  theme: initial,
  toggle: () =>
    set((s) => {
      const next = s.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      return { theme: next };
    }),
  setTheme: (t) => {
    applyTheme(t);
    set({ theme: t });
  },
}));
