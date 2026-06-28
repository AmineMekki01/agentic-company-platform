import type { AgentSetting, AgentSettingCreate, DbUser, KnowledgeSource } from "@/lib/api";
import { Settings, Wrench, BookOpen, Workflow, Globe, History, ThumbsUp, Activity, Sparkles } from "lucide-react";

export type TabKey = "overview" | "tools" | "skills" | "knowledge" | "agent-to-agent" | "deploy" | "versions" | "feedback" | "evaluation";

export const ALL_TABS: { key: TabKey; label: string; icon: typeof Settings }[] = [
  { key: "overview", label: "Overview", icon: Settings },
  { key: "tools", label: "Tools", icon: Wrench },
  { key: "skills", label: "Skills", icon: Sparkles },
  { key: "knowledge", label: "Knowledge", icon: BookOpen },
  { key: "agent-to-agent", label: "Agent-to-Agent", icon: Workflow },
  { key: "deploy", label: "Deploy", icon: Globe },
  { key: "versions", label: "Versions", icon: History },
  { key: "feedback", label: "Feedback", icon: ThumbsUp },
  { key: "evaluation", label: "Evaluation", icon: Activity },
];

export const AVAILABLE_TOOLS = ["web_search", "create_jira_ticket"];

export const DEFAULT_NEW_AGENT: AgentSettingCreate = {
  slug: "",
  name: "",
  description: "",
  llm_model: "gpt-5.4-nano",
  system_prompt: "",
  retrieval_top_k: 5,
  connected_sources: [],
  tools: [],
  is_orchestrator: false,
  is_router: false,
  routes_to: [],
  visibility: "all",
  created_by: "",
  allow_uploads: true,
  allowed_users: [],
};

export const formatUserLabel = (u: DbUser) => [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email;

export const formatDateTime = (value: string | null | undefined) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};

export function diffWords(oldText: string, newText: string): { type: "same" | "del" | "ins"; text: string }[] {
  const oldWords = oldText.split(/(\s+)/).filter(Boolean);
  const newWords = newText.split(/(\s+)/).filter(Boolean);
  const m = oldWords.length;
  const n = newWords.length;
  const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = oldWords[i] === newWords[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const result: { type: "same" | "del" | "ins"; text: string }[] = [];
  let i = 0, j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && oldWords[i] === newWords[j]) {
      result.push({ type: "same", text: oldWords[i] });
      i++; j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({ type: "ins", text: newWords[j] });
      j++;
    } else if (i < m) {
      result.push({ type: "del", text: oldWords[i] });
      i++;
    } else {
      break;
    }
  }
  return result;
}

export function resolveSourceNames(ids: string[] | null | undefined, sourceList: KnowledgeSource[]): string {
  if (!ids || ids.length === 0) return "—";
  return ids.map((id) => sourceList.find((s) => s.id === id)?.name || id).join(", ");
}

export function mergeAgentDraft(agent: AgentSetting): AgentSetting {
  if (!agent.draft_config || Object.keys(agent.draft_config).length === 0) return agent;
  const draft = agent.draft_config;
  const merged: AgentSetting = { ...agent };
  if ("name" in draft) merged.name = draft.name as string | null;
  if ("description" in draft) merged.description = draft.description as string | null;
  if ("llm_model" in draft) merged.llm_model = draft.llm_model as string | null;
  if ("system_prompt" in draft) merged.system_prompt = draft.system_prompt as string | null;
  if ("retrieval_top_k" in draft) merged.retrieval_top_k = draft.retrieval_top_k as number;
  if ("connected_sources" in draft) merged.connected_sources = draft.connected_sources as string[] | null;
  if ("tools" in draft) merged.tools = draft.tools as string[] | null;
  if ("is_orchestrator" in draft) merged.is_orchestrator = draft.is_orchestrator as boolean;
  if ("routes_to" in draft) merged.routes_to = draft.routes_to as string[] | null;
  if ("visibility" in draft) merged.visibility = draft.visibility as string;
  if ("created_by" in draft) merged.created_by = draft.created_by as string | null;
  if ("allow_uploads" in draft) merged.allow_uploads = draft.allow_uploads as boolean;
  if ("allowed_users" in draft) merged.allowed_users = draft.allowed_users as string[] | null;
  if ("beta_users" in draft) merged.beta_users = draft.beta_users as string[] | null;
  if ("mode_profile" in draft) merged.mode_profile = draft.mode_profile as Record<string, unknown> | null;
  if ("agent_type" in draft) merged.agent_type = draft.agent_type as string;
  if ("research_config" in draft) merged.research_config = draft.research_config as AgentSetting["research_config"];
  return merged;
}

export const makeDefaultNewAgent = (ownerEmail = ""): AgentSettingCreate => ({
  ...DEFAULT_NEW_AGENT,
  created_by: ownerEmail,
});

export function hasDraftChanges(agent: AgentSetting | null): boolean {
  if (!agent) return false;
  if (!agent.is_published) return false;
  return agent.draft_config !== null && Object.keys(agent.draft_config).length > 0;
}
