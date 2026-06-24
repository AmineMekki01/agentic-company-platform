import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/stores/theme";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-tertiary transition hover:bg-hover hover:text-secondary"
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
    >
      {theme === "dark" ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </button>
  );
}
