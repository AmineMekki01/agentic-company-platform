import { FileText } from "lucide-react";

const ICON_MAP: Record<string, string> = {
  notion: "/icons/notion.svg",
  jira: "/icons/jira.svg",
  s3: "/icons/s3.svg",
  gdrive: "/icons/gdrive.svg",
};

interface ServiceIconProps {
  type: string;
  size?: number;
  className?: string;
}

export default function ServiceIcon({ type, size = 24, className = "" }: ServiceIconProps) {
  const path = ICON_MAP[type.toLowerCase()];

  if (path) {
    return (
      <img
        src={path}
        alt={type}
        width={size}
        height={size}
        className={`inline-block object-contain ${className}`}
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }

  return <FileText className={`text-tertiary ${className}`} style={{ width: size, height: size }} />;
}
