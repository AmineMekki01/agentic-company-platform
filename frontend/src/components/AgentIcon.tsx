import { Bot, Briefcase, HeartPulse } from "lucide-react";

interface AgentIconProps {
  slug: string;
  size?: number;
  className?: string;
}

export default function AgentIcon({ slug, size = 24, className = "" }: AgentIconProps) {
  switch (slug.toLowerCase()) {
    case "hr":
      return <HeartPulse className={`text-rose-400 ${className}`} style={{ width: size, height: size }} />;
    case "it":
      return <Bot className={`text-cyan-400 ${className}`} style={{ width: size, height: size }} />;
    default:
      return <Briefcase className={`text-neutral-400 ${className}`} style={{ width: size, height: size }} />;
  }
}
