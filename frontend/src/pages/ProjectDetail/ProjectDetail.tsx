import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { type ContentItem, type ContentPerformance } from '../../api/client';
import { CalendarPanel } from './CalendarPanel';
import { EditPlanModal } from './EditPlanModal';
import { EditProjectModal } from './EditProjectModal';
import { PerformanceModal } from './PerformanceModal';
import { PerformancePanel } from './PerformancePanel';
import { PositioningPanel } from './PositioningPanel';
import { ProjectOverviewSection } from './ProjectOverviewSection';
import { ScriptModal } from './ScriptModal';
import { StoreGrowthPanel } from './StoreGrowthPanel';
import { useProjectDetailActions } from './useProjectDetailActions';
import { usePlanningTaskState } from './usePlanningTaskState';
import { useProjectDetailData } from './useProjectDetailData';
import './ProjectDetail.css';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeItem, setActiveItem] = useState<ContentItem | null>(null);
  const [showFullPlan, setShowFullPlan] = useState(true);
  const [showEditProject, setShowEditProject] = useState(false);
  const [showEditPlan, setShowEditPlan] = useState(false);
  const [showPerformanceModal, setShowPerformanceModal] = useState(false);
  const [editingPerformance, setEditingPerformance] = useState<ContentPerformance | null>(null);
  const {
    project,
    isLoading,
    storeGrowthPlan,
    positioning,
    strategy,
    currentStage,
    hasStrategy,
    hasCalendar,
    performanceList,
    performanceSummary,
    performanceRecap,
    nextTopicBatch,
    calendarDisplayItems,
    referenceNames,
    referenceScopeItems,
  } = useProjectDetailData(id);
  const {
    scriptTaskMap,
    visibleCalendarItems,
    pendingRegenerationDaySet,
    isStrategyRegenerating,
  } = usePlanningTaskState({
    projectId: id,
    project,
    currentStage,
    hasStrategy,
    calendarDisplayItems,
  });
  const {
    generateStrategyMutation,
    regenerateCalendarMutation,
    generatePerformanceRecapMutation,
    generateNextTopicBatchMutation,
    importNextTopicBatchItemMutation,
    removePerformanceMutation,
    refreshProject,
    refreshPerformance,
  } = useProjectDetailActions({
    projectId: id,
    project,
    hasStrategy,
    hasCalendar,
    calendarDisplayItems,
  });

  if (isLoading) {
    return (
      <div className="project-detail-loading">
        <div className="spinner project-detail-loading-spinner" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="empty-state">
        <div className="empty-title">项目不存在</div>
        <Link to="/planning" className="btn btn-primary project-detail-back-btn">返回列表</Link>
      </div>
    );
  }

  return (
    <div className="project-detail-page animate-fade-in">
      <ProjectOverviewSection
        project={project}
        currentStage={currentStage}
        hasStrategy={hasStrategy}
        hasCalendar={hasCalendar}
        referenceNames={referenceNames}
        referenceScopeItems={referenceScopeItems}
        isGenerateStrategyPending={generateStrategyMutation.isPending}
        isRegenerateCalendarPending={regenerateCalendarMutation.isPending}
        onGenerateStrategy={() => generateStrategyMutation.mutate()}
        onGenerateCalendar={() => {
          setActiveItem(null);
          void regenerateCalendarMutation.mutateAsync([]);
        }}
        onEditProject={() => setShowEditProject(true)}
      />

      {storeGrowthPlan ? (
        <StoreGrowthPanel
          storeGrowthPlan={storeGrowthPlan}
          currentStage={currentStage}
          isExpanded={showFullPlan}
          isRegenerating={isStrategyRegenerating}
          isRegeneratePending={generateStrategyMutation.isPending}
          onToggleExpand={() => setShowFullPlan((current) => !current)}
          onRegenerate={() => generateStrategyMutation.mutate()}
          onEdit={() => setShowEditPlan(true)}
        />
      ) : positioning && (
        <PositioningPanel
          positioning={positioning}
          strategy={strategy}
          currentStage={currentStage}
          isExpanded={showFullPlan}
          isRegenerating={isStrategyRegenerating}
          isRegeneratePending={generateStrategyMutation.isPending}
          onToggleExpand={() => setShowFullPlan((current) => !current)}
          onRegenerate={() => generateStrategyMutation.mutate()}
          onEdit={() => setShowEditPlan(true)}
        />
      )}

      <CalendarPanel
        projectId={id!}
        hasStrategy={hasStrategy}
        hasCalendar={hasCalendar}
        currentStage={currentStage}
        calendarDisplayItems={visibleCalendarItems}
        pendingRegenerationDaySet={pendingRegenerationDaySet}
        scriptTaskMap={scriptTaskMap}
        onOpenItem={(item) => setActiveItem(item)}
        onRegenerate={async (dayNumbers) => {
          setActiveItem(null);
          return regenerateCalendarMutation.mutateAsync(dayNumbers);
        }}
        isRegeneratePending={regenerateCalendarMutation.isPending}
        regenerateError={regenerateCalendarMutation.isError ? (regenerateCalendarMutation.error as Error) : null}
      />

      <PerformancePanel
        contentItems={project.content_items || []}
        performanceList={performanceList}
        performanceSummary={performanceSummary}
        performanceRecap={performanceRecap}
        nextTopicBatch={nextTopicBatch}
        isGeneratingRecap={generatePerformanceRecapMutation.isPending}
        generateRecapError={generatePerformanceRecapMutation.isError ? (generatePerformanceRecapMutation.error as Error) : null}
        onGenerateRecap={() => generatePerformanceRecapMutation.mutate()}
        isGeneratingNextTopics={generateNextTopicBatchMutation.isPending}
        generateNextTopicsError={generateNextTopicBatchMutation.isError ? (generateNextTopicBatchMutation.error as Error) : null}
        onGenerateNextTopics={() => generateNextTopicBatchMutation.mutate()}
        isImportingNextTopic={importNextTopicBatchItemMutation.isPending}
        importNextTopicError={importNextTopicBatchItemMutation.isError ? (importNextTopicBatchItemMutation.error as Error) : null}
        onImportNextTopic={(itemIndex) => importNextTopicBatchItemMutation.mutate({ itemIndex })}
        isRemovingPerformance={removePerformanceMutation.isPending}
        onRemovePerformance={(performanceId) => removePerformanceMutation.mutate(performanceId)}
        onCreatePerformance={() => {
          setEditingPerformance(null);
          setShowPerformanceModal(true);
        }}
        onEditPerformance={(row) => {
          setEditingPerformance(row);
          setShowPerformanceModal(true);
        }}
      />

      {activeItem && (
        <ScriptModal
          item={(project.content_items || []).find((ci) => ci.id === activeItem.id) || activeItem}
          projectId={id!}
          taskStatus={scriptTaskMap.get(activeItem.id)?.status || null}
          taskMessage={scriptTaskMap.get(activeItem.id)?.message || null}
          onClose={() => setActiveItem(null)}
        />
      )}

      {showEditProject && (
        <EditProjectModal
          project={project}
          onClose={() => setShowEditProject(false)}
          onSaved={() => {
            refreshProject();
            setShowEditProject(false);
          }}
        />
      )}

      {showEditPlan && project.account_plan && (
        <EditPlanModal
          projectId={id!}
          plan={project.account_plan}
          onClose={() => setShowEditPlan(false)}
          onSaved={() => {
            refreshProject();
            setShowEditPlan(false);
          }}
        />
      )}

      {showPerformanceModal && (
        <PerformanceModal
          projectId={id!}
          contentItems={project.content_items || []}
          editing={editingPerformance}
          onClose={() => setShowPerformanceModal(false)}
          onSaved={() => {
            setShowPerformanceModal(false);
            setEditingPerformance(null);
            refreshPerformance();
          }}
        />
      )}
    </div>
  );
}
