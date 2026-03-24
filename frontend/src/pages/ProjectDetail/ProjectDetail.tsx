import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { planningApi, type ContentItem, type ContentPerformance, type TaskCenterItem, type TaskCenterListResponse } from '../../api/client';
import { ArrowLeft, Loader2, ChevronDown, ChevronUp, Sparkles, Calendar, Pencil, RefreshCw } from '../../components/Icons';
import { CalendarPanel } from './CalendarPanel';
import { EditPlanModal } from './EditPlanModal';
import { EditProjectModal } from './EditProjectModal';
import { PerformanceModal } from './PerformanceModal';
import { PerformancePanel } from './PerformancePanel';
import { ScriptModal } from './ScriptModal';
import { upsertOptimisticTask } from './projectDetailShared';
import { usePlanningTaskState } from './usePlanningTaskState';
import { useProjectDetailData } from './useProjectDetailData';
import './ProjectDetail.css';

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [activeItem, setActiveItem] = useState<ContentItem | null>(null);
  const [showFullPlan, setShowFullPlan] = useState(true);
  const [showEditProject, setShowEditProject] = useState(false);
  const [showEditPlan, setShowEditPlan] = useState(false);
  const [showPerformanceModal, setShowPerformanceModal] = useState(false);
  const [editingPerformance, setEditingPerformance] = useState<ContentPerformance | null>(null);
  const {
    project,
    isLoading,
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

  const generateStrategyMutation = useMutation({
    mutationFn: () => planningApi.generateStrategy(id!),
    onMutate: async () => {
      const optimisticTask: TaskCenterItem = {
        id: `optimistic-strategy-${id}`,
        task_key: `planning:${id}:generate-strategy`,
        task_type: 'planning_generate',
        title: `生成定位：${project?.client_name || id}`,
        entity_type: 'planning_project',
        entity_id: id!,
        status: 'queued',
        progress_step: 'queued',
        message: '定位生成任务已提交',
        context: {
          planning_state: 'strategy_regenerating',
          has_existing_strategy: hasStrategy,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const previousTaskPage = qc.getQueryData<TaskCenterListResponse>(['project-planning-tasks', id]);
      qc.setQueryData<TaskCenterListResponse>(['project-planning-tasks', id], (current) => upsertOptimisticTask(current, optimisticTask));
      return { previousTaskPage };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', id] });
      qc.invalidateQueries({ queryKey: ['project-planning-tasks', id] });
    },
    onError: (_error, _variables, context) => {
      qc.setQueryData(['project-planning-tasks', id], context?.previousTaskPage);
    },
  });

  const regenerateCalendarMutation = useMutation({
    mutationFn: (dayNumbers: number[]) => planningApi.regenerateCalendar(id!, { regenerate_day_numbers: dayNumbers }),
    onMutate: async (dayNumbers) => {
      const fallbackDayNumbers = calendarDisplayItems.length > 0
        ? calendarDisplayItems.map((item) => item.day_number)
        : (project?.content_calendar || []).map((item) => item.day);
      const isPartialRegeneration = dayNumbers.length > 0 && hasCalendar;
      const targetDays = (dayNumbers.length > 0 ? dayNumbers : fallbackDayNumbers)
        .filter((dayNumber, index, source) => source.indexOf(dayNumber) === index)
        .sort((a, b) => a - b);
      const snapshots = calendarDisplayItems
        .filter((item) => targetDays.includes(item.day_number))
        .map((item) => ({
          id: item.id,
          day_number: item.day_number,
          title_direction: item.title_direction,
          content_type: item.content_type || null,
          tags: item.tags || [],
          is_script_generated: item.is_script_generated,
          calendar_meta: item.calendarMeta || (project?.content_calendar || []).find((calendarItem) => calendarItem.day === item.day_number) || null,
        }));
      const optimisticTask: TaskCenterItem = {
        id: `optimistic-calendar-${id}`,
        task_key: `planning:${id}:calendar`,
        task_type: 'planning_calendar',
        title: `${hasCalendar ? '重生成日历' : '生成日历'}：${project?.client_name || id}`,
        entity_type: 'planning_project',
        entity_id: id!,
        status: 'queued',
        progress_step: 'queued',
        message: isPartialRegeneration
          ? `已提交局部重生成任务，将重写 Day ${targetDays.join(', ')}`
          : '30天日历生成任务已提交',
        context: {
          planning_state: 'calendar_regenerating',
          regeneration_mode: isPartialRegeneration ? 'partial' : (hasCalendar ? 'full' : 'initial'),
          regenerate_day_numbers: targetDays,
          calendar_snapshots: snapshots,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const previousTaskPage = qc.getQueryData<TaskCenterListResponse>(['project-planning-tasks', id]);
      qc.setQueryData<TaskCenterListResponse>(['project-planning-tasks', id], (current) => upsertOptimisticTask(current, optimisticTask));
      return { previousTaskPage };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', id] });
      qc.invalidateQueries({ queryKey: ['project-planning-tasks', id] });
    },
    onError: (_error, _variables, context) => {
      qc.setQueryData(['project-planning-tasks', id], context?.previousTaskPage);
    },
  });

  const generatePerformanceRecapMutation = useMutation({
    mutationFn: () => planningApi.generatePerformanceRecap(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const generateNextTopicBatchMutation = useMutation({
    mutationFn: () => planningApi.generateNextTopicBatch(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const importNextTopicBatchItemMutation = useMutation({
    mutationFn: ({ itemIndex }: { itemIndex: number }) => planningApi.importNextTopicBatchItem(id!, itemIndex),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const removePerformanceMutation = useMutation({
    mutationFn: (performanceId: string) => planningApi.removePerformance(id!, performanceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project-performance', id] });
      qc.invalidateQueries({ queryKey: ['project-performance-summary', id] });
    },
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
      {/* 顶部导航 */}
      <div className="detail-breadcrumb">
        <Link to="/planning" className="btn btn-ghost btn-sm">
          <ArrowLeft size={14} /> 返回列表
        </Link>
        <span className={`badge ${
          currentStage === 'completed' ? 'badge-green' :
          currentStage === 'strategy_completed' ? 'badge-blue' :
          currentStage === 'strategy_generating' || currentStage === 'calendar_generating' ? 'badge-yellow' : 'badge-purple'
        }`}>
          {currentStage === 'completed' ? '已完成' :
            currentStage === 'strategy_completed' ? '定位已完成' :
            currentStage === 'strategy_generating' ? '定位生成中...' :
            currentStage === 'calendar_generating' ? '日历生成中...' : '草稿'}
        </span>
      </div>

      {/* 项目标题 */}
      <div className="detail-hero">
        <div className="detail-hero-main">
          <div className="detail-hero-pill">账号策划详情</div>
          <h1 className="page-title">{project.client_name}</h1>
          <div className="detail-hero-meta">
            <span className="badge badge-purple">{project.industry}</span>
            <span className="detail-hero-audience">{project.target_audience}</span>
          </div>
          {referenceNames.length > 0 && (
            <div className="detail-hero-reference-row">
              <span className="detail-hero-reference-label">参考 IP</span>
              <div className="detail-hero-reference-list">
                {referenceNames.map((name) => (
                  <span key={name} className="detail-hero-reference-chip">
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {currentStage === 'draft' && (
            <button className="btn btn-primary btn-sm" onClick={() => generateStrategyMutation.mutate()} disabled={generateStrategyMutation.isPending}>
              <Sparkles size={13} /> {generateStrategyMutation.isPending ? '生成中...' : '生成账号定位方案'}
            </button>
          )}
          {(currentStage === 'strategy_completed' || (hasStrategy && !hasCalendar && currentStage !== 'calendar_generating')) && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setActiveItem(null);
                void regenerateCalendarMutation.mutateAsync([]);
              }}
              disabled={regenerateCalendarMutation.isPending}
            >
              <Calendar size={13} /> {regenerateCalendarMutation.isPending ? '生成中...' : '生成30天日历'}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => setShowEditProject(true)}>
            <Pencil size={13} /> 编辑信息
          </button>
        </div>
      </div>

      {currentStage === 'strategy_generating' && (
        <div className="generating-tip">
          <Loader2 size={16} className="spin-icon" />
          AI 正在生成账号定位方案，请稍等...（页面会自动刷新）
        </div>
      )}
      {currentStage === 'calendar_generating' && (
        <div className="generating-tip generating-tip-info">
          <Loader2 size={16} className="spin-icon" />
          AI 正在生成 30 天内容日历方案，请稍等...（期间您可以继续浏览和编辑上方账号策略）
        </div>
      )}

      {!hasStrategy && currentStage === 'draft' && (
        <div className="card detail-section">
          <div className="empty-state" style={{ padding: '24px 16px' }}>
            <div className="empty-title">先生成账号定位方案</div>
            <div className="empty-desc">先确认核心定位、人设标签、内容支柱和表达策略，再进入 30 天日历生成，能明显降低超时和整批返工。</div>
            <button className="btn btn-primary" onClick={() => generateStrategyMutation.mutate()} disabled={generateStrategyMutation.isPending}>
              <Sparkles size={14} /> {generateStrategyMutation.isPending ? '生成中...' : '开始生成账号定位方案'}
            </button>
          </div>
        </div>
      )}

      {referenceNames.length > 0 && (
        <div className="detail-reference-scope-card">
          <div className="detail-reference-scope-head">
            <div>
              <div className="detail-reference-scope-eyebrow">参考 IP 应用说明</div>
              <h2>下面这份策划具体参考了什么</h2>
            </div>
            <div className="detail-reference-scope-tags">
              {referenceNames.map((name) => (
                <span key={name} className="detail-reference-scope-chip">
                  {name}
                </span>
              ))}
            </div>
          </div>
          <div className="detail-reference-scope-grid">
            {referenceScopeItems.map((item) => (
              <div key={item} className="detail-reference-scope-item">
                <span className="detail-reference-scope-dot" />
                <p>{item}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 账号定位 */}
      {positioning && (
        <div className={`card detail-section detail-positioning ${isStrategyRegenerating ? 'detail-positioning-regenerating' : ''}`}>
          <div
            className={`detail-section-head ${showFullPlan ? 'is-open' : ''}`}
            onClick={() => setShowFullPlan(!showFullPlan)}
          >
            <h2 className="section-title detail-section-title">账号定位方案</h2>
            <div className="flex items-center gap-2 detail-section-actions" onClick={e => e.stopPropagation()}>
              {currentStage !== 'strategy_generating' && currentStage !== 'calendar_generating' && (
                <button className="btn btn-ghost btn-sm" onClick={() => generateStrategyMutation.mutate()} disabled={generateStrategyMutation.isPending}>
                  <RefreshCw size={13} /> {generateStrategyMutation.isPending ? '生成中...' : '重新生成定位'}
                </button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => setShowEditPlan(true)}>
                <Pencil size={13} /> 编辑
              </button>
              {showFullPlan ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>

          {showFullPlan && (
            <div className="detail-positioning-body animate-fade-in">
              {/* 核心定位 */}
              {positioning.core_identity && (
                <div className="identity-block">
                  <div className="identity-label">核心定位 slogan</div>
                  <div className="identity-value gradient-text">{positioning.core_identity}</div>
                </div>
              )}

              {/* 主页简介 */}
              {positioning.bio_suggestion && (
                <div className="bio-block">
                  <div className="identity-label">主页简介建议</div>
                  <div className="bio-text">{positioning.bio_suggestion}</div>
                </div>
              )}

              {(positioning.target_audience_detail || positioning.differentiation || positioning.user_value || positioning.follow_reason) && (
                <div className="strategy-grid">
                  {positioning.target_audience_detail && (
                    <div className="strategy-item">
                      <div className="identity-label">受众细化</div>
                      <div className="strategy-value">{positioning.target_audience_detail}</div>
                    </div>
                  )}
                  {positioning.differentiation && (
                    <div className="strategy-item">
                      <div className="identity-label">差异化支点</div>
                      <div className="strategy-value">{positioning.differentiation}</div>
                    </div>
                  )}
                  {positioning.user_value && (
                    <div className="strategy-item">
                      <div className="identity-label">用户持续获得什么</div>
                      <div className="strategy-value">{positioning.user_value}</div>
                    </div>
                  )}
                  {positioning.follow_reason && (
                    <div className="strategy-item">
                      <div className="identity-label">用户为什么会关注</div>
                      <div className="strategy-value">{positioning.follow_reason}</div>
                    </div>
                  )}
                </div>
              )}

              {/* 人设标签 */}
              {positioning.personality_tags && (
                <div className="positioning-block">
                  <div className="identity-label positioning-label">人设标签</div>
                  <div className="positioning-tags">
                    {positioning.personality_tags.map(tag => (
                      <span key={tag} className="badge badge-purple">{tag}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 内容支柱 */}
              {positioning.content_pillars && (
                <div className="positioning-block">
                  <div className="identity-label positioning-label">内容支柱</div>
                  <div className="pillars-grid">
                    {positioning.content_pillars.map(p => (
                      <div key={p.name} className="pillar-card">
                        <div className="pillar-name">{p.name}</div>
                        <div className="pillar-ratio">{p.ratio}</div>
                        <div className="pillar-desc">{p.description}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 内容策略 */}
              {strategy && (
                <div className="strategy-grid">
                  <div className="strategy-item">
                    <div className="identity-label">发布频率</div>
                    <div className="strategy-value">{strategy.posting_frequency}</div>
                  </div>
                  <div className="strategy-item">
                    <div className="identity-label">内容形式</div>
                    <div className="strategy-value">{strategy.primary_format}</div>
                  </div>
                  <div className="strategy-item">
                    <div className="identity-label">最佳发布时间</div>
                    <div className="strategy-value">{strategy.best_posting_times?.join('、')}</div>
                  </div>
                  <div className="strategy-item">
                    <div className="identity-label">内容基调</div>
                    <div className="strategy-value">{strategy.content_tone}</div>
                  </div>
                  {strategy.stop_scroll_reason && (
                    <div className="strategy-item">
                      <div className="identity-label">用户为什么会停下来继续看</div>
                      <div className="strategy-value">{strategy.stop_scroll_reason}</div>
                    </div>
                  )}
                  {strategy.interaction_trigger && (
                    <div className="strategy-item">
                      <div className="identity-label">互动触发点</div>
                      <div className="strategy-value">{strategy.interaction_trigger}</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          {isStrategyRegenerating && (
            <div className="detail-positioning-overlay">
              <span className="detail-positioning-overlay-badge">
                <Loader2 size={14} className="spin-icon" /> 重新生成定位中
              </span>
            </div>
          )}
        </div>
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
            qc.invalidateQueries({ queryKey: ['project', id] });
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
            qc.invalidateQueries({ queryKey: ['project', id] });
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
            qc.invalidateQueries({ queryKey: ['project-performance', id] });
            qc.invalidateQueries({ queryKey: ['project-performance-summary', id] });
          }}
        />
      )}
    </div>
  );
}
