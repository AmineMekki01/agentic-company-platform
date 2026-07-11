import { Loader2, Save, ChevronLeft, AlertTriangle, Eye, EyeOff, RotateCcw, Rocket } from "lucide-react";
import type {
  AgentSetting, AgentSettingCreate, AgentVersion, AgentVersionDetail,
  AgentFeedbackSummary, MessageFeedback, AgentEvalTestSetDetail, AgentEvalRun,
  AgentEvalRunDetail, AgentEvalSchedule, DbUser, KnowledgeSource, UploadSettings,
  ModelOption, Skill, SkillCreate,
} from "@/lib/api";
import AgentIcon from "@/components/AgentIcon";
import { ALL_TABS, hasDraftChanges, type TabKey } from "./agentUtils";
import OverviewTab from "./tabs/OverviewTab";
import ToolsTab from "./tabs/ToolsTab";
import SkillsTab from "./tabs/SkillsTab";
import KnowledgeTab from "./tabs/KnowledgeTab";
import DeployTab from "./tabs/DeployTab";
import AgentToAgentTab from "./tabs/AgentToAgentTab";
import VersionsTab from "./tabs/VersionsTab";
import FeedbackTab from "./tabs/FeedbackTab";
import EvalTab from "./tabs/EvalTab";
import VersionDiffModal from "./modals/VersionDiffModal";
import FeedbackDetailModal from "./modals/FeedbackDetailModal";
import { PublishModal, TestDraftModal } from "./modals/SimpleModals";
import { LaunchRunModal, RunDetailModal, ContextModal } from "./modals/EvalModals";

interface Props {
  selected: AgentSetting;
  agents: AgentSetting[];
  sources: KnowledgeSource[];
  users: DbUser[];
  models: ModelOption[];
  uploadSettings: UploadSettings | null;
  activeTab: TabKey;
  setActiveTab: (t: TabKey) => void;
  setSelected: (a: AgentSetting) => void;
  onClose: () => void;
  saving: boolean;
  onSave: () => void;

  toggleTool: (agent: AgentSetting | AgentSettingCreate, tool: string) => void;
  toggleRoute: (agent: AgentSetting | AgentSettingCreate, slug: string) => void;
  toggleAllowedUser: (agent: AgentSetting | AgentSettingCreate, email: string) => void;

  versions: AgentVersion[];
  restoring: boolean;
  onViewVersion: (versionId: string) => void;
  onRestoreVersion: (versionId: string) => void;
  versionDetail: AgentVersionDetail | null;
  onCloseVersionDetail: () => void;

  feedbackSummary: AgentFeedbackSummary | null;
  feedbackList: MessageFeedback[];
  feedbackLoading: boolean;
  selectedFeedback: MessageFeedback | null;
  onSelectFeedback: (f: MessageFeedback) => void;
  onCloseFeedback: () => void;

  showPublishModal: boolean;
  publishNotes: string;
  setPublishNotes: (v: string) => void;
  publishing: boolean;
  onPublish: () => void;
  onOpenPublishModal: () => void;
  onDiscardDraft: () => void;
  onClosePublishModal: () => void;

  showTestDraft: boolean;
  testDraftMessage: string;
  setTestDraftMessage: (v: string) => void;
  testDraftResponse: string;
  testDraftTraceUrl?: string | null;
  testingDraft: boolean;
  onOpenTestDraft: () => void;
  onTestDraft: () => void;
  onCloseTestDraft: () => void;

  evalTestSets: AgentEvalTestSetDetail[];
  evalRuns: AgentEvalRun[];
  evalLoading: boolean;
  evalSubTab: "tests" | "runs" | "schedules";
  setEvalSubTab: (t: "tests" | "runs" | "schedules") => void;
  evalSchedules: AgentEvalSchedule[];
  onSchedulesChanged: () => void;
  onTestDataChanged: () => void;

  showLaunchRunModal: boolean;
  launchRunForm: { name: string; thresholds: Record<string, number>; selectedTestSetIds: Set<string> };
  setLaunchRunForm: (fn: (p: any) => any) => void;
  onLaunchRun: () => void;
  onConfirmLaunchRun: () => void;
  onCloseLaunchRunModal: () => void;

  selectedEvalRun: AgentEvalRunDetail | null;
  onViewRun: (run: AgentEvalRun) => void;
  onCloseRunDetail: () => void;
  onDeleteRun: (run: AgentEvalRun) => void;

  selectedContext: string | null;
  onSelectContext: (ctx: string) => void;
  onCloseContext: () => void;

  agentSkills: Skill[];
  sharedSkills: Skill[];
  assignedSkillIds: Set<string>;
  skillsLoading: boolean;
  onCreateAgentSkill: (body: SkillCreate) => Promise<void>;
  onUpdateAgentSkill: (skillId: string, body: Partial<SkillCreate>) => Promise<void>;
  onDeleteAgentSkill: (skillId: string) => Promise<void>;
  onToggleAgentSkill: (skillId: string) => Promise<void>;
  onBatchAssignSkills: (assign: string[], unassign: string[]) => Promise<void>;
}

export default function AgentDetailPanel(props: Props) {
  const s = props.selected;
  const visibleTabs = s.agent_type === "deep_research"
    ? ALL_TABS.filter((t) => ["overview", "knowledge", "deploy", "versions", "feedback"].includes(t.key))
    : ALL_TABS;

  return (
    <div className="flex-1 min-w-0 h-full">
      <div className="bg-card border border-line rounded-xl shadow-sm flex flex-col h-full">
        <div className="flex items-center justify-between px-5 py-4 border-b border-line">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={props.onClose}
              className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-3 py-2 text-sm text-secondary transition hover:bg-hover"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to list
            </button>
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand/10 border border-brand/20">
                <AgentIcon slug={s.slug} size={18} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-primary">{s.name || s.slug}</h2>
                  {s.is_published ? (
                    hasDraftChanges(s) ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-medium text-warning border border-warning/20">
                        <AlertTriangle className="h-3 w-3" />
                        Modified
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success border border-success/20">
                        <Eye className="h-3 w-3" />
                        Published
                      </span>
                    )
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-hover/70 px-2 py-0.5 text-[11px] font-medium text-secondary border border-line/70">
                      <EyeOff className="h-3 w-3" />
                      Draft
                    </span>
                  )}
                </div>
                <span className="text-xs text-tertiary uppercase tracking-wide">{s.slug}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {s.is_published && hasDraftChanges(s) && (
              <>
                <button
                  onClick={() => { props.setTestDraftMessage(""); props.onOpenTestDraft(); }}
                  className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
                >
                  <Eye className="h-3.5 w-3.5" />
                  Test Draft
                </button>
                <button
                  onClick={props.onDiscardDraft}
                  className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Discard
                </button>
                <button
                  onClick={props.onOpenPublishModal}
                  className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
                >
                  <Rocket className="h-3.5 w-3.5" />
                  Publish
                </button>
              </>
            )}
            {!s.is_published && (
              <button
                onClick={props.onOpenPublishModal}
                className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
              >
                <Rocket className="h-3.5 w-3.5" />
                Publish
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-1 min-h-0">
          <div className="w-56 shrink-0 border-r border-line bg-canvas p-3 h-full overflow-y-auto">
            <div className="mb-3 px-2 text-[11px] font-medium uppercase tracking-wide text-tertiary">
              Sections
            </div>
            <div className="space-y-1">
              {visibleTabs.map((t: typeof ALL_TABS[number]) => {
                const Icon = t.icon;
                const active = props.activeTab === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => props.setActiveTab(t.key)}
                    className={
                      "flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition " +
                      (active
                        ? "border-brand/20 bg-brand/10 font-medium text-primary"
                        : "border-transparent text-tertiary hover:border-line hover:bg-hover hover:text-primary")
                    }
                  >
                    <Icon className={"h-4 w-4 " + (active ? "text-brand" : "text-tertiary")} />
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {props.activeTab === "overview" && (
              <OverviewTab selected={s} setSelected={props.setSelected} users={props.users} models={props.models} />
            )}
            {props.activeTab === "tools" && (
              <ToolsTab selected={s} setSelected={props.setSelected} toggleTool={props.toggleTool} />
            )}
            {props.activeTab === "skills" && (
              <SkillsTab
                agentSlug={s.slug}
                agentSkills={props.agentSkills}
                sharedSkills={props.sharedSkills}
                assignedSkillIds={props.assignedSkillIds}
                loading={props.skillsLoading}
                onCreateSkill={props.onCreateAgentSkill}
                onUpdateSkill={props.onUpdateAgentSkill}
                onDeleteSkill={props.onDeleteAgentSkill}
                onToggleSkill={props.onToggleAgentSkill}
                onBatchAssign={props.onBatchAssignSkills}
              />
            )}
            {props.activeTab === "knowledge" && (
              <KnowledgeTab selected={s} setSelected={props.setSelected} sources={props.sources} uploadSettings={props.uploadSettings} />
            )}
            {props.activeTab === "deploy" && (
              <DeployTab selected={s} setSelected={props.setSelected} users={props.users} toggleAllowedUser={props.toggleAllowedUser} />
            )}
            {props.activeTab === "agent-to-agent" && (
              <AgentToAgentTab selected={s} setSelected={props.setSelected} agents={props.agents} toggleRoute={props.toggleRoute} />
            )}
            {props.activeTab === "versions" && (
              <VersionsTab versions={props.versions} restoring={props.restoring} onViewVersion={props.onViewVersion} onRestoreVersion={props.onRestoreVersion} />
            )}
            {props.activeTab === "feedback" && (
              <FeedbackTab feedbackSummary={props.feedbackSummary} feedbackList={props.feedbackList} feedbackLoading={props.feedbackLoading} onSelectFeedback={props.onSelectFeedback} />
            )}
            {props.activeTab === "evaluation" && (
              <EvalTab
                evalTestSets={props.evalTestSets}
                evalRuns={props.evalRuns}
                evalLoading={props.evalLoading}
                evalSubTab={props.evalSubTab}
                setEvalSubTab={props.setEvalSubTab}
                agentSlug={props.selected.slug}
                evalSchedules={props.evalSchedules}
                onSchedulesChanged={props.onSchedulesChanged}
                onTestDataChanged={props.onTestDataChanged}
                onLaunchRun={props.onLaunchRun}
                onViewRun={props.onViewRun}
                onDeleteRun={props.onDeleteRun}
              />
            )}
          </div>
        </div>

        <div className="flex justify-end px-5 py-4 border-t border-line">
          <button
            onClick={props.onSave}
            disabled={props.saving}
            className="flex items-center gap-1.5 bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 disabled:opacity-50 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition shadow-lg shadow-brand/15"
          >
            {props.saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {props.saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>

      {props.showPublishModal && (
        <PublishModal
          isPublished={s.is_published}
          publishNotes={props.publishNotes}
          setPublishNotes={props.setPublishNotes}
          publishing={props.publishing}
          onCancel={props.onClosePublishModal}
          onPublish={props.onPublish}
        />
      )}

      {props.versionDetail && (
        <VersionDiffModal versionDetail={props.versionDetail} selected={s} sources={props.sources} onClose={props.onCloseVersionDetail} />
      )}

      {props.selectedFeedback && (
        <FeedbackDetailModal feedback={props.selectedFeedback} onClose={props.onCloseFeedback} />
      )}

      {props.showTestDraft && (
        <TestDraftModal
          testDraftMessage={props.testDraftMessage}
          setTestDraftMessage={props.setTestDraftMessage}
          testDraftResponse={props.testDraftResponse}
          testDraftTraceUrl={props.testDraftTraceUrl}
          testingDraft={props.testingDraft}
          onCancel={props.onCloseTestDraft}
          onSend={props.onTestDraft}
        />
      )}

      {props.showLaunchRunModal && (
        <LaunchRunModal
          launchRunForm={props.launchRunForm}
          setLaunchRunForm={props.setLaunchRunForm}
          evalTestSets={props.evalTestSets}
          onClose={props.onCloseLaunchRunModal}
          onLaunch={props.onConfirmLaunchRun}
        />
      )}

      {props.selectedEvalRun && (
        <RunDetailModal
          run={props.selectedEvalRun}
          onClose={props.onCloseRunDetail}
          onContextClick={props.onSelectContext}
        />
      )}

      {props.selectedContext && (
        <ContextModal context={props.selectedContext} onClose={props.onCloseContext} />
      )}
    </div>
  );
}
