import { FileText, Globe, Upload } from "lucide-react";

const ICON_MAP: Record<string, string> = {
  notion: "/icons/notion.svg",
  jira: "/icons/jira.svg",
  s3: "/icons/s3.svg",
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
          // If the image fails to load, hide it so the fallback isn't duplicated
          (e.target as HTMLImageElement).style.display = "none";
        }}
      />
    );
  }

  // Fallback Lucide icons for types without a downloaded logo
  switch (type.toLowerCase()) {
    case "upload":
      return <Upload className={`text-amber-400 ${className}`} style={{ width: size, height: size }} />;
    case "web":
      return <Globe className={`text-emerald-400 ${className}`} style={{ width: size, height: size }} />;
    default:
      return <FileText className={`text-neutral-400 ${className}`} style={{ width: size, height: size }} />;
  }
}
