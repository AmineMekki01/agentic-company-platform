import { Bot, Briefcase, HeartPulse } from "lucide-react";

interface AgentIconProps {
  slug: string;
  size?: number;
  className?: string;
}

export default function AgentIcon({ slug, size = 24, className = "" }: AgentIconProps) {
  switch (slug.toLowerCase()) {
    case "hr":
      return <HeartPulse className={`text-danger ${className}`} style={{ width: size, height: size }} />;
    case "it":
      return <Bot className={`text-brand ${className}`} style={{ width: size, height: size }} />;
    default:
      return <Briefcase className={`text-tertiary ${className}`} style={{ width: size, height: size }} />;
  }
}
