import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Plus, RefreshCw, Bot } from "lucide-react";
import { api, type AgentSetting, type AgentSettingCreate, type KnowledgeSource, type DbUser, type AgentVersion, type AgentVersionDetail, type MessageFeedback, type AgentFeedbackSummary, type AgentEvalTestSetDetail, type AgentEvalRun, type AgentEvalRunDetail, type AgentEvalSchedule, type UploadSettings, type ModelOption, type Skill, type SkillCreate } from "@/lib/api";
import AgentListTable from "@/components/admin/agents/AgentListTable";
import CreateAgentPanel from "@/components/admin/agents/CreateAgentPanel";
import AdminPageHeader from "@/components/admin/AdminPageHeader";
import AgentDetailPanel from "@/components/admin/agents/AgentDetailPanel";
import { DeleteConfirmModal } from "@/components/admin/agents/modals/SimpleModals";
import { useAuth } from "@/stores/auth";
import { mergeAgentDraft, makeDefaultNewAgent, type TabKey } from "@/components/admin/agents/agentUtils";

export default function AdminAgents() {
  const { user: currentUser } = useAuth();
  const { agentSlug: urlAgentSlug } = useParams();
  const navigate = useNavigate();
  const didAutoOpen = useRef(false);
  const [agents, setAgents] = useState<AgentSetting[]>([]);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [users, setUsers] = useState<DbUser[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selected, setSelected] = useState<AgentSetting | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSettingCreate>(() => makeDefaultNewAgent());
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [versions, setVersions] = useState<AgentVersion[]>([]);
  const [feedbackList, setFeedbackList] = useState<MessageFeedback[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<AgentFeedbackSummary | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [selectedFeedback, setSelectedFeedback] = useState<MessageFeedback | null>(null);
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishNotes, setPublishNotes] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [versionDetail, setVersionDetail] = useState<AgentVersionDetail | null>(null);
  const [showTestDraft, setShowTestDraft] = useState(false);
  const [testDraftMessage, setTestDraftMessage] = useState("");
  const [testDraftResponse, setTestDraftResponse] = useState("");
  const [testingDraft, setTestingDraft] = useState(false);

  const [evalTestSets, setEvalTestSets] = useState<AgentEvalTestSetDetail[]>([]);
  const [evalRuns, setEvalRuns] = useState<AgentEvalRun[]>([]);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalSubTab, setEvalSubTab] = useState<"tests" | "runs" | "schedules">("tests");
  const [showLaunchRunModal, setShowLaunchRunModal] = useState(false);
  const [launchRunForm, setLaunchRunForm] = useState<{
    name: string;
    thresholds: Record<string, number>;
    selectedTestSetIds: Set<string>;
  }>({
    name: "",
    thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
    selectedTestSetIds: new Set<string>(),
  });
  const [selectedEvalRun, setSelectedEvalRun] = useState<AgentEvalRunDetail | null>(null);
  const [evalSchedules, setEvalSchedules] = useState<AgentEvalSchedule[]>([]);
  const [selectedContext, setSelectedContext] = useState<string | null>(null);
  const [uploadSettings, setUploadSettings] = useState<UploadSettings | null>(null);
  const [agentSkills, setAgentSkills] = useState<Skill[]>([]);
  const [sharedSkills, setSharedSkills] = useState<Skill[]>([]);
  const [assignedSkillIds, setAssignedSkillIds] = useState<Set<string>>(new Set());
  const [skillsLoading, setSkillsLoading] = useState(false);

  const closeSelected = () => {
    setSelected(null);
    setActiveTab("overview");
    navigate("/admin/agents");
  };

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [agentData, sourceData, userData, modelData, uploadData] = await Promise.all([
        api.listAgentSettings(),
        api.listKnowledgeSources(),
        api.listUsers(),
        api.listModels(),
        api.getUploadSettings().catch(() => null),
      ]);
      setUploadSettings(uploadData);
      const mergedAgents = agentData.map(mergeAgentDraft);
      setAgents(mergedAgents);
      setSources(sourceData);
      setUsers(userData);
      setModels(modelData);

      if (urlAgentSlug && !didAutoOpen.current) {
        const target = mergedAgents.find((a) => a.slug === urlAgentSlug) ?? null;
        if (target) {
          setSelected(target);
          setActiveTab("overview");
        }
        didAutoOpen.current = true;
      } else if (selected) {
        const updated = mergedAgents.find((a) => a.slug === selected.slug);
        if (updated) setSelected(updated);
      }
    } catch (e: any) {
      setError(e.message || "Failed to load agents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const loadVersions = useCallback(async (slug: string) => {
    try {
      const data = await api.listAgentVersions(slug);
      setVersions(data);
    } catch {
      setVersions([]);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "versions") {
      loadVersions(selected.slug);
    }
  }, [selected, activeTab, loadVersions]);

  const loadFeedback = useCallback(async (slug: string) => {
    setFeedbackLoading(true);
    try {
      const [list, summary] = await Promise.all([
        api.getAgentFeedback(slug),
        api.getAgentFeedbackSummary(slug),
      ]);
      setFeedbackList(list);
      setFeedbackSummary(summary);
    } catch {
      setFeedbackList([]);
      setFeedbackSummary(null);
    } finally {
      setFeedbackLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "feedback") {
      loadFeedback(selected.slug);
    }
  }, [selected, activeTab, loadFeedback]);

  const loadEvalData = useCallback(async (slug: string) => {
    setEvalLoading(true);
    try {
      const [testSets, runs, schedules] = await Promise.all([
        api.listEvalTestSets(slug),
        api.listEvalRuns(slug),
        api.listEvalSchedules(slug),
      ]);
      setEvalTestSets(testSets);
      setEvalRuns(runs);
      setEvalSchedules(schedules);
    } catch {
      setEvalTestSets([]);
      setEvalRuns([]);
      setEvalSchedules([]);
    } finally {
      setEvalLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "evaluation") {
      loadEvalData(selected.slug);
    }
  }, [selected, activeTab, loadEvalData]);

  const loadSkills = useCallback(async (slug: string) => {
    setSkillsLoading(true);
    try {
      const [agentSkillList, allShared] = await Promise.all([
        api.listAgentSkills(slug),
        api.listAllSkills(),
      ]);
      setAgentSkills(agentSkillList.filter((s) => s.scope === "agent"));
      const shared = allShared.filter((s) => s.scope === "shared");
      setSharedSkills(shared);
      const assigned = new Set(agentSkillList.filter((s) => s.scope === "shared").map((s) => s.id));
      setAssignedSkillIds(assigned);
    } catch {
      setAgentSkills([]);
      setSharedSkills([]);
      setAssignedSkillIds(new Set());
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected && activeTab === "skills") {
      loadSkills(selected.slug);
    }
  }, [selected, activeTab, loadSkills]);

  const handleCreateAgentSkill = async (body: SkillCreate) => {
    if (!selected) return;
    await api.createAgentSkill(selected.slug, body);
    await loadSkills(selected.slug);
  };

  const handleUpdateAgentSkill = async (skillId: string, body: Partial<SkillCreate>) => {
    if (!selected) return;
    await api.updateAgentSkill(selected.slug, skillId, body);
    await loadSkills(selected.slug);
  };

  const handleDeleteAgentSkill = async (skillId: string) => {
    if (!selected) return;
    await api.deleteAgentSkill(selected.slug, skillId);
    await loadSkills(selected.slug);
  };

  const handleToggleAgentSkill = async (skillId: string) => {
    if (!selected) return;
    await api.toggleAgentSkill(selected.slug, skillId);
    await loadSkills(selected.slug);
  };

  const handleBatchAssignSkills = async (assign: string[], unassign: string[]) => {
    if (!selected) return;
    await api.batchUpdateAgentSkills(selected.slug, { assign, unassign });
    await loadSkills(selected.slug);
  };

  const handlePublish = async () => {
    if (!selected) return;
    setPublishing(true);
    setError(null);
    try {
      await api.publishAgent(selected.slug, { notes: publishNotes.trim() || undefined });
      setShowPublishModal(false);
      setPublishNotes("");
      await refresh();
    } catch (e: any) {
      setError(e.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  const handleDiscardDraft = async () => {
    if (!selected) return;
    setError(null);
    try {
      await api.discardAgentDraft(selected.slug);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Discard failed");
    }
  };

  const handleRestoreVersion = async (versionId: string) => {
    if (!selected) return;
    setRestoring(true);
    setError(null);
    try {
      await api.restoreAgentVersion(selected.slug, versionId);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Restore failed");
    } finally {
      setRestoring(false);
    }
  };

  const handleViewVersion = async (versionId: string) => {
    if (!selected) return;
    try {
      const detail = await api.getAgentVersion(selected.slug, versionId);
      setVersionDetail(detail);
    } catch (e: any) {
      setError(e.message || "Failed to load version");
    }
  };

  const handleTestDraft = async () => {
    if (!selected || !testDraftMessage.trim()) return;
    setTestingDraft(true);
    setError(null);
    try {
      const res = await api.testAgentDraft(selected.slug, { message: testDraftMessage } as any);
      setTestDraftResponse((res as any).response || (res as any).output || JSON.stringify(res));
    } catch (e: any) {
      setTestDraftResponse(e.message || "Test failed");
    } finally {
      setTestingDraft(false);
    }
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    setError(null);
    try {
      const { id, slug, created_at, updated_at, is_published, published_at, draft_config, ...rest } = selected;
      await api.updateAgentSetting(selected.slug, rest as any);
      await refresh();
    } catch (e: any) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const create = async () => {
    if (!newAgent.slug.trim()) {
      setError("Slug is required");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      await api.createAgentSetting(newAgent);
      setShowCreate(false);
      setNewAgent(makeDefaultNewAgent(currentUser?.email || ""));
      await refresh();
    } catch (e: any) {
      setError(e.message || "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const remove = async (slug: string) => {
    setError(null);
    try {
      await api.deleteAgentSetting(slug);
      setDeleteConfirm(null);
      if (selected?.slug === slug) closeSelected();
      await refresh();
    } catch (e: any) {
      setError(e.message || "Delete failed");
    }
  };

  const toggleTool = (agent: AgentSetting | AgentSettingCreate, tool: string) => {
    const current = agent.tools || [];
    const next = current.includes(tool)
      ? current.filter((t) => t !== tool)
      : [...current, tool];
    if ("id" in agent) {
      setSelected({ ...(agent as AgentSetting), tools: next });
    } else {
      setNewAgent({ ...agent, tools: next });
    }
  };

  const toggleRoute = (agent: AgentSetting | AgentSettingCreate, slug: string) => {
    const current = agent.routes_to || [];
    const next = current.includes(slug)
      ? current.filter((s) => s !== slug)
      : [...current, slug];
    if ("id" in agent) {
      setSelected({ ...(agent as AgentSetting), routes_to: next });
    } else {
      setNewAgent({ ...agent, routes_to: next });
    }
  };

  const toggleAllowedUser = (agent: AgentSetting | AgentSettingCreate, email: string) => {
    const current = agent.allowed_users || [];
    const next = current.includes(email)
      ? current.filter((e) => e !== email)
      : [...current, email];
    if ("id" in agent) {
      setSelected({ ...(agent as AgentSetting), allowed_users: next });
    } else {
      setNewAgent({ ...agent, allowed_users: next });
    }
  };

  const handleLaunchRun = () => {
    setLaunchRunForm({
      name: `Run ${new Date().toLocaleString()}`,
      thresholds: { answer_correctness: 0.5, faithfulness: 0.5, answer_relevancy: 0.5 },
      selectedTestSetIds: new Set(evalTestSets.map((ts) => ts.id)),
    });
    setShowLaunchRunModal(true);
  };

  const handleConfirmLaunchRun = async () => {
    if (!selected) return;
    if (!launchRunForm.name.trim() || launchRunForm.selectedTestSetIds.size === 0) return;
    try {
      await api.createEvalRun(selected.slug, {
        name: launchRunForm.name,
        test_set_ids: Array.from(launchRunForm.selectedTestSetIds),
        thresholds: launchRunForm.thresholds,
      });
      setShowLaunchRunModal(false);
      setEvalSubTab("runs");
      loadEvalData(selected.slug);
      try {
        const agents = await api.listAgentSettings();
        const updated = agents.find((a) => a.slug === selected.slug);
        if (updated) setSelected(updated);
      } catch { /* ignore */ }
    } catch {
      alert("Failed to launch run");
    }
  };

  const handleViewRun = async (run: AgentEvalRun) => {
    if (!selected) return;
    try {
      const detail = await api.getEvalRunDetail(selected.slug, run.id);
      setSelectedEvalRun(detail);
    } catch {
      alert("Failed to load run details");
    }
  };

  const handleDeleteRun = async (run: AgentEvalRun) => {
    if (!selected) return;
    if (!confirm("Delete this run?")) return;
    try {
      await api.deleteEvalRun(selected.slug, run.id);
      loadEvalData(selected.slug);
      try {
        const agents = await api.listAgentSettings();
        const updated = agents.find((a) => a.slug === selected.slug);
        if (updated) setSelected(updated);
      } catch { /* ignore */ }
    } catch {
      alert("Failed to delete run");
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <AdminPageHeader
        title="Agents"
        description="Configure and manage AI agents for your workspace"
        icon={Bot}
      >
        <button
          onClick={() => { setShowCreate(true); setError(null); setNewAgent(makeDefaultNewAgent(currentUser?.email || "")); }}
          className="flex items-center gap-1.5 text-sm bg-gradient-to-br from-brand to-violet-600 hover:from-brand-hover hover:to-violet-500 px-3 py-2 rounded-lg font-medium text-white transition shadow-lg shadow-brand/15"
        >
          <Plus className="h-3.5 w-3.5" />
          Create Agent
        </button>
        <button
          onClick={refresh}
          className="flex items-center gap-1.5 text-sm bg-card hover:bg-hover border border-line/60 px-3 py-2 rounded-lg transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </AdminPageHeader>

      {error && (
        <div className="mb-4 bg-danger-soft border border-danger/30 text-danger text-sm px-4 py-3 rounded-xl flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-danger shrink-0" />
          {error}
        </div>
      )}

      <div className="flex gap-4 flex-1 min-h-0">
        <div className={selected ? "hidden" : "w-full"}>
          <AgentListTable
            agents={agents}
            users={users}
            loading={loading}
            selectedSlug={selected?.slug ?? null}
            onSelect={(slug: string) => {
              const a = agents.find((ag) => ag.slug === slug);
              if (a) {
                setSelected(a);
                setActiveTab("overview");
                navigate(`/admin/agents/${slug}`);
              }
            }}
            onDelete={(slug: string) => setDeleteConfirm(slug)}
          />
        </div>

        <div className={selected ? "flex-1 min-w-0 h-full" : "hidden"}>
          {selected ? (
            <AgentDetailPanel
              selected={selected}
              agents={agents}
              sources={sources}
              users={users}
              models={models}
              uploadSettings={uploadSettings}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              setSelected={setSelected}
              onClose={closeSelected}
              saving={saving}
              onSave={save}
              toggleTool={toggleTool}
              toggleRoute={toggleRoute}
              toggleAllowedUser={toggleAllowedUser}
              versions={versions}
              restoring={restoring}
              onViewVersion={handleViewVersion}
              onRestoreVersion={handleRestoreVersion}
              versionDetail={versionDetail}
              onCloseVersionDetail={() => setVersionDetail(null)}
              feedbackSummary={feedbackSummary}
              feedbackList={feedbackList}
              feedbackLoading={feedbackLoading}
              selectedFeedback={selectedFeedback}
              onSelectFeedback={setSelectedFeedback}
              onCloseFeedback={() => setSelectedFeedback(null)}
              showPublishModal={showPublishModal}
              publishNotes={publishNotes}
              setPublishNotes={setPublishNotes}
              publishing={publishing}
              onPublish={handlePublish}
              onOpenPublishModal={() => setShowPublishModal(true)}
              onDiscardDraft={handleDiscardDraft}
              onClosePublishModal={() => { setShowPublishModal(false); setPublishNotes(""); }}
              showTestDraft={showTestDraft}
              testDraftMessage={testDraftMessage}
              setTestDraftMessage={setTestDraftMessage}
              testDraftResponse={testDraftResponse}
              testingDraft={testingDraft}
              onOpenTestDraft={() => setShowTestDraft(true)}
              onTestDraft={handleTestDraft}
              onCloseTestDraft={() => { setShowTestDraft(false); setTestDraftMessage(""); setTestDraftResponse(""); }}
              evalTestSets={evalTestSets}
              evalRuns={evalRuns}
              evalLoading={evalLoading}
              evalSubTab={evalSubTab}
              setEvalSubTab={setEvalSubTab}
              evalSchedules={evalSchedules}
              onSchedulesChanged={() => selected && loadEvalData(selected.slug)}
              onTestDataChanged={() => selected && loadEvalData(selected.slug)}
              showLaunchRunModal={showLaunchRunModal}
              launchRunForm={launchRunForm}
              setLaunchRunForm={setLaunchRunForm}
              onLaunchRun={handleLaunchRun}
              onConfirmLaunchRun={handleConfirmLaunchRun}
              onCloseLaunchRunModal={() => setShowLaunchRunModal(false)}
              selectedEvalRun={selectedEvalRun}
              onViewRun={handleViewRun}
              onCloseRunDetail={() => setSelectedEvalRun(null)}
              onDeleteRun={handleDeleteRun}
              selectedContext={selectedContext}
              onSelectContext={setSelectedContext}
              onCloseContext={() => setSelectedContext(null)}
              agentSkills={agentSkills}
              sharedSkills={sharedSkills}
              assignedSkillIds={assignedSkillIds}
              skillsLoading={skillsLoading}
              onCreateAgentSkill={handleCreateAgentSkill}
              onUpdateAgentSkill={handleUpdateAgentSkill}
              onDeleteAgentSkill={handleDeleteAgentSkill}
              onToggleAgentSkill={handleToggleAgentSkill}
              onBatchAssignSkills={handleBatchAssignSkills}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-tertiary">
              <Bot className="h-10 w-10 text-tertiary mb-3" />
              <p className="text-sm">Select an agent to configure</p>
            </div>
          )}
        </div>
      </div>

      <CreateAgentPanel
        open={showCreate}
        onClose={() => { setShowCreate(false); setError(null); }}
        agent={newAgent}
        onChange={setNewAgent}
        onCreate={create}
        creating={creating}
        users={users}
        models={models}
        agents={agents}
        currentUserEmail={currentUser?.email}
        error={error}
        onClearError={() => setError(null)}
        uploadSettings={uploadSettings}
      />

      {deleteConfirm && (
        <DeleteConfirmModal
          slug={deleteConfirm}
          onCancel={() => setDeleteConfirm(null)}
          onConfirm={() => remove(deleteConfirm)}
        />
      )}
    </div>
  );
}
