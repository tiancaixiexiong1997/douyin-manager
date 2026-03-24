import { useMemo, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toPng } from 'html-to-image';
import { bloggerApi, downloadApi, planningApi, taskApi, type ContentCalendarItem, type ContentItem, type ContentPerformance, type ContentPerformanceCreateRequest, type VideoScript, type UpdatePlanningRequest, type TaskCenterItem, type TaskCenterListResponse } from '../../api/client';
import { CustomSelect } from '../../components/CustomSelect';
import { ArrowLeft, FileText, Loader2, ChevronDown, ChevronUp, Sparkles, Calendar, Pencil, Save, X, RefreshCw, Plus, Trash2, TrendingUp, Download } from '../../components/Icons';
import { formatBackendDateTime, toBackendTimestamp } from '../../utils/datetime';
import { notifyError, notifyInfo, notifySuccess } from '../../utils/notify';
import './ProjectDetail.css';

type ScriptTaskStatus = TaskCenterItem['status'] | null;
type CalendarDisplayItem = ContentItem & { calendarMeta?: ContentCalendarItem | null };
type PendingCalendarRegeneration = {
  dayNumbers: number[];
  snapshotsByDay: Record<number, CalendarDisplayItem>;
};
type PlanningTaskContext = {
  planning_state?: string;
  has_existing_strategy?: boolean;
  regeneration_mode?: 'initial' | 'full' | 'partial';
  regenerate_day_numbers?: number[];
  calendar_snapshots?: Array<{
    id: string;
    day_number: number;
    title_direction: string;
    content_type?: string | null;
    tags?: string[] | null;
    is_script_generated?: boolean;
    calendar_meta?: ContentCalendarItem | null;
  }>;
};
const SCHEDULE_GROUP_FILTER_PREFIX = 'schedule_group:';
type ProjectStage = 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed';

function inferProjectStage(project: {
  status: string;
  account_plan?: {
    account_positioning?: unknown;
    content_strategy?: unknown;
    calendar_generation_meta?: unknown;
  } | null;
}): ProjectStage {
  const hasStrategy = Boolean(project.account_plan?.account_positioning || project.account_plan?.content_strategy);
  const hasCalendar = Boolean(project.account_plan?.calendar_generation_meta);
  if (project.status === 'strategy_generating') return 'strategy_generating';
  if (project.status === 'strategy_completed') return 'strategy_completed';
  if (project.status === 'calendar_generating') return 'calendar_generating';
  if (project.status === 'completed') return 'completed';
  if (project.status === 'in_progress') {
    return hasStrategy && hasCalendar ? 'calendar_generating' : 'strategy_generating';
  }
  return hasStrategy ? (hasCalendar ? 'completed' : 'strategy_completed') : 'draft';
}

function normalizeCalendarContentType(value?: string | null): string {
  const raw = String(value || '').trim();
  if (!raw) return '口播+画中画';
  const compact = raw.toLowerCase().replace(/\s+/g, '');
  if (compact.includes('口播') || compact.includes('画中画')) return '口播+画中画';
  if (compact.includes('vlog') || raw.includes('跟拍') || raw.includes('记录')) return '跟拍Vlog';
  if (raw.includes('评测') || raw.includes('测评')) return '测评';
  if (raw.includes('教程') || raw.includes('教学')) return '教程';
  if (raw.includes('探店')) return '探店实拍';
  return raw;
}

function deriveCalendarBatchGroup(contentType?: string | null): string {
  const text = normalizeCalendarContentType(contentType);
  if (text.includes('口播') || text.includes('画中画')) return '办公室口播组';
  if (text.includes('教程')) return '教程演示组';
  if (text.includes('测评')) return '测评演示组';
  if (text.includes('探店') || text.includes('实拍')) return '门店实拍组';
  if (text.includes('Vlog') || text.includes('跟拍')) return '门店跟拍组';
  return '办公室口播组';
}

function deriveScheduleMeta(contentType?: string | null): {
  shootFormat: string;
  talentRequirement: string;
  shootScene: string;
  estimatedDuration: string;
  prepRequirement: string;
  scheduleGroup: string;
} {
  const text = normalizeCalendarContentType(contentType);
  if (text.includes('口播') || text.includes('画中画')) {
    return {
      shootFormat: '口播',
      talentRequirement: 'IP单人出镜',
      shootScene: '办公室',
      estimatedDuration: '15分钟内',
      prepRequirement: '需提词器',
      scheduleGroup: '办公室口播组',
    };
  }
  if (text.includes('教程')) {
    return {
      shootFormat: '演示',
      talentRequirement: 'IP单人出镜',
      shootScene: '演示区',
      estimatedDuration: '15分钟内',
      prepRequirement: '需道具',
      scheduleGroup: '教程演示组',
    };
  }
  if (text.includes('测评')) {
    return {
      shootFormat: '演示',
      talentRequirement: 'IP单人出镜',
      shootScene: '产品展示区',
      estimatedDuration: '15分钟内',
      prepRequirement: '需道具',
      scheduleGroup: '测评演示组',
    };
  }
  if (text.includes('探店') || text.includes('实拍')) {
    return {
      shootFormat: '实拍讲解',
      talentRequirement: 'IP单人出镜',
      shootScene: '门店现场',
      estimatedDuration: '30分钟内',
      prepRequirement: '需现场配合',
      scheduleGroup: '门店实拍组',
    };
  }
  if (text.includes('Vlog') || text.includes('跟拍')) {
    return {
      shootFormat: '跟拍',
      talentRequirement: 'IP单人出镜',
      shootScene: '门店现场',
      estimatedDuration: '30分钟内',
      prepRequirement: '需流程提纲',
      scheduleGroup: '门店跟拍组',
    };
  }
  return {
    shootFormat: '口播',
    talentRequirement: 'IP单人出镜',
    shootScene: '办公室',
    estimatedDuration: '15分钟内',
    prepRequirement: '需提词器',
    scheduleGroup: '办公室口播组',
  };
}

function getCalendarScheduleMeta(item: CalendarDisplayItem): {
  shootFormat: string;
  talentRequirement: string;
  shootScene: string;
  estimatedDuration: string;
  prepRequirement: string;
  scheduleGroup: string;
} {
  const profile = deriveScheduleMeta(item.calendarMeta?.content_type || item.content_type);
  return {
    shootFormat: item.calendarMeta?.shoot_format?.trim() || profile.shootFormat,
    talentRequirement: item.calendarMeta?.talent_requirement?.trim() || profile.talentRequirement,
    shootScene: item.calendarMeta?.shoot_scene?.trim() || profile.shootScene,
    estimatedDuration: item.calendarMeta?.estimated_duration?.trim() || profile.estimatedDuration,
    prepRequirement: item.calendarMeta?.prep_requirement?.trim() || profile.prepRequirement,
    scheduleGroup: item.calendarMeta?.schedule_group?.trim() || item.calendarMeta?.batch_shoot_group?.trim() || profile.scheduleGroup || deriveCalendarBatchGroup(item.calendarMeta?.content_type || item.content_type),
  };
}

function formatMetricNumber(value?: number | null): string {
  return Number(value || 0).toLocaleString('zh-CN');
}

function formatMetricPercent(value?: number | null): string {
  return value != null ? `${Number(value).toFixed(1)}%` : '-';
}

function formatDateTime(value?: string | null): string {
  return formatBackendDateTime(value);
}

function getPerformanceEngagementRate(row: Pick<ContentPerformance, 'views' | 'likes' | 'comments' | 'shares'>): number | null {
  if (!row.views) return null;
  return ((row.likes + row.comments + row.shares) / row.views) * 100;
}

function getContentItemLabel(item?: Pick<ContentItem, 'day_number' | 'title_direction'> | null): string {
  if (!item) return '未关联策划条目';
  return `第 ${item.day_number} 天 · ${item.title_direction}`;
}

function getPerformanceHighlightMeta(
  item: ContentPerformance | null | undefined,
  kind: 'views' | 'completion' | 'engagement' | 'conversion'
): string {
  if (!item) return '暂无数据';
  if (kind === 'views') return `${formatMetricNumber(item.views)} 播放`;
  if (kind === 'completion') return item.completion_rate != null ? `${Number(item.completion_rate).toFixed(1)}% 完播率` : '暂无完播率';
  if (kind === 'engagement') {
    const rate = getPerformanceEngagementRate(item);
    return rate != null ? `${rate.toFixed(1)}% 互动率` : '暂无互动率';
  }
  if (item.conversions > 0 && item.views > 0) {
    return `${item.conversions} 转化 · ${(item.conversions / item.views * 100).toFixed(2)}% 转化率`;
  }
  if (item.conversions > 0) return `${item.conversions} 转化`;
  return '暂无转化';
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isPendingTask(task?: TaskCenterItem | null): boolean {
  return task?.status === 'queued' || task?.status === 'running';
}

function parsePlanningTaskContext(task?: TaskCenterItem | null): PlanningTaskContext | null {
  const context = task?.context;
  if (!context || typeof context !== 'object') return null;
  return context as PlanningTaskContext;
}

function buildPendingCalendarRegeneration(task?: TaskCenterItem | null): PendingCalendarRegeneration | null {
  if (!isPendingTask(task)) return null;
  const context = parsePlanningTaskContext(task);
  if (!context || context.planning_state !== 'calendar_regenerating') return null;

  const dayNumbers = Array.from(new Set((context.regenerate_day_numbers || []).filter((value): value is number => Number.isInteger(value) && value >= 1 && value <= 30))).sort((a, b) => a - b);
  if (dayNumbers.length === 0) return null;

  const snapshotsByDay: Record<number, CalendarDisplayItem> = {};
  for (const snapshot of context.calendar_snapshots || []) {
    if (!snapshot || !Number.isInteger(snapshot.day_number)) continue;
    snapshotsByDay[snapshot.day_number] = {
      id: snapshot.id,
      day_number: snapshot.day_number,
      title_direction: snapshot.title_direction,
      content_type: snapshot.content_type || undefined,
      tags: snapshot.tags || undefined,
      is_script_generated: Boolean(snapshot.is_script_generated),
      full_script: undefined,
      calendarMeta: snapshot.calendar_meta || null,
    };
  }

  return { dayNumbers, snapshotsByDay };
}

function upsertOptimisticTask(
  current: TaskCenterListResponse | undefined,
  task: TaskCenterItem,
): TaskCenterListResponse {
  const items = [task, ...(current?.items || []).filter((item) => item.task_key !== task.task_key)];
  return {
    items,
    total: Math.max(current?.total || 0, items.length),
    skip: current?.skip || 0,
    limit: current?.limit || 20,
    has_more: false,
    summary: current?.summary || {},
  };
}

function sanitizeFilename(value: string): string {
  return value
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80) || 'script';
}

function ScriptModal({
  item,
  projectId,
  taskStatus,
  taskMessage,
  onClose,
}: {
  item: ContentItem;
  projectId: string;
  taskStatus: ScriptTaskStatus;
  taskMessage?: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [script, setScript] = useState<VideoScript | null>(item.full_script || null);
  const [isEditing, setIsEditing] = useState(false);
  const [editScript, setEditScript] = useState<VideoScript | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const exportImageRef = useRef<HTMLDivElement | null>(null);
  const isTaskRunning = taskStatus === 'queued' || taskStatus === 'running';

  const generateMutation = useMutation({
    mutationFn: () => planningApi.generateScript(item.id),
    onSuccess: (data) => {
      setScript(data.script);
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (s: VideoScript) => planningApi.updateContentItem(item.id, { full_script: s }),
    onSuccess: () => {
      setScript(editScript);
      setIsEditing(false);
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const startEdit = () => {
    setEditScript(JSON.parse(JSON.stringify(script)));
    setIsEditing(true);
  };

  const exportBaseName = useMemo(() => {
    return sanitizeFilename(`第${item.day_number}天-${item.title_direction}`);
  }, [item.day_number, item.title_direction]);

  const handleExportLongImage = async () => {
    if (!script || isEditing || isExporting) return;
    if (!exportImageRef.current) {
      notifyInfo('当前还没有可导出的脚本内容');
      return;
    }

    try {
      setIsExporting(true);
      notifyInfo('正在生成脚本图片，请稍等');
      if (typeof document !== 'undefined' && 'fonts' in document) {
        await (document as Document & { fonts?: FontFaceSet }).fonts?.ready;
      }
      await sleep(80);

      const dataUrl = await toPng(exportImageRef.current, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: '#f8fafc',
      });

      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${exportBaseName}-完整脚本长图.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifySuccess('已导出完整脚本长图');
    } catch (error) {
      notifyError(`导出脚本长图失败：${(error as Error).message || '请稍后再试'}`);
    } finally {
      setIsExporting(false);
    }
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal script-modal animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">第 {item.day_number} 天内容</h2>
            <p className="page-subtitle" style={{ marginTop: 4 }}>{item.title_direction}</p>
          </div>
          <div className="flex items-center gap-2">
            {script && !isEditing && (
              <button className="btn btn-ghost btn-sm" onClick={handleExportLongImage} disabled={isExporting}>
                <Download size={13} /> {isExporting ? '导出中...' : '导出脚本长图'}
              </button>
            )}
            {script && !isEditing && (
              <button className="btn btn-ghost btn-sm" onClick={startEdit}>
                <Pencil size={13} /> 编辑
              </button>
            )}
            {isEditing && (
              <>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={saveMutation.isPending}
                  onClick={() => editScript && saveMutation.mutate(editScript)}
                >
                  <Save size={13} /> {saveMutation.isPending ? '保存中...' : '保存'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => setIsEditing(false)}>
                  <X size={13} /> 取消
                </button>
              </>
            )}
            <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={16} /></button>
          </div>
        </div>

        {!script && !generateMutation.isPending && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div className="empty-icon" style={{ margin: '0 auto 16px' }}>
              <FileText size={24} />
            </div>
            <p className="text-secondary" style={{ marginBottom: 20 }}>
              点击下方按钮，AI 将根据账号定位和参考博主风格，生成完整视频脚本
            </p>
            {isTaskRunning ? (
              <div className="text-secondary" style={{ fontSize: 13 }}>
                已有脚本任务在后台执行中，请稍后自动刷新查看。
              </div>
            ) : (
              <button className="btn btn-primary" onClick={() => generateMutation.mutate()}>
                <Sparkles size={15} /> 生成完整脚本
              </button>
            )}
          </div>
        )}

        {(generateMutation.isPending || isTaskRunning) && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Loader2 size={32} className="text-secondary" style={{ animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
            <p className="text-secondary">{taskMessage || 'AI 正在为你生成脚本，请稍等...'}</p>
          </div>
        )}

        {generateMutation.isError && (
          <div className="error-tip" style={{ marginBottom: 12 }}>
            {(generateMutation.error as Error).message}
          </div>
        )}

        {script && !isEditing && (
          <div className="script-content animate-fade-in">
            {script.title_options && (
              <div className="script-section">
                <div className="script-section-title">📝 标题备选</div>
                <div className="title-options">
                  {script.title_options.map((t, i) => (
                    <div key={i} className="title-option">{t}</div>
                  ))}
                </div>
              </div>
            )}
            {script.hook_script && (
              <div className="script-section">
                <div className="script-section-title">⚡ 黄金3秒开头</div>
                <div className="script-text">{script.hook_script}</div>
              </div>
            )}
            {script.storyboard && (
              <div className="script-section">
                <div className="script-section-title">🎬 分镜脚本</div>
                <div className="storyboard">
                  {script.storyboard.map((scene) => (
                    <div key={scene.scene} className="storyboard-scene">
                      <div className="scene-header">
                        <span className="scene-num">Scene {scene.scene}</span>
                        <span className="scene-duration">{scene.duration}</span>
                      </div>
                      <div className="scene-body">
                        <div className="scene-row"><span className="scene-label">画面</span>{scene.visual}</div>
                        <div className="scene-row"><span className="scene-label">台词</span>{scene.script}</div>
                        <div className="scene-row"><span className="scene-label">拍摄</span>{scene.camera}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {script.caption_template && (
              <div className="script-section">
                <div className="script-section-title">📱 发布文案</div>
                <div className="script-text">{script.caption_template}</div>
              </div>
            )}
            {script.hashtag_suggestions && (
              <div className="script-section">
                <div className="script-section-title">🏷️ 话题标签</div>
                <div className="hashtags">
                  {script.hashtag_suggestions.map(tag => (
                    <span key={tag} className="badge badge-purple">#{tag}</span>
                  ))}
                </div>
              </div>
            )}
            <div className="modal-footer" style={{ justifyContent: 'center' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => generateMutation.mutate()} disabled={isTaskRunning || generateMutation.isPending}>
                <Sparkles size={13} /> 重新生成
              </button>
            </div>
          </div>
        )}

        {isEditing && editScript && (
          <div className="script-content animate-fade-in">
            <div className="script-section">
              <div className="script-section-title">📝 标题备选</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={3}
                value={editScript.title_options?.join('\n') || ''}
                onChange={e => setEditScript(s => ({ ...s!, title_options: e.target.value.split('\n') }))}
                placeholder="每行一个标题"
              />
            </div>
            <div className="script-section">
              <div className="script-section-title">⚡ 黄金3秒开头</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={3}
                value={editScript.hook_script || ''}
                onChange={e => setEditScript(s => ({ ...s!, hook_script: e.target.value }))}
              />
            </div>
            {editScript.storyboard && (
              <div className="script-section">
                <div className="script-section-title">🎬 分镜脚本</div>
                <div className="storyboard">
                  {editScript.storyboard.map((scene, idx) => (
                    <div key={scene.scene} className="storyboard-scene">
                      <div className="scene-header">
                        <span className="scene-num">Scene {scene.scene}</span>
                        <input className="form-input" style={{ fontSize: 12, padding: '2px 8px', width: 80 }}
                          value={scene.duration}
                          onChange={e => setEditScript(s => {
                            const sb = [...(s!.storyboard || [])];
                            sb[idx] = { ...sb[idx], duration: e.target.value };
                            return { ...s!, storyboard: sb };
                          })}
                        />
                      </div>
                      <div className="scene-body">
                        {(['visual', 'script', 'camera'] as const).map(field => (
                          <div key={field} className="scene-row">
                            <span className="scene-label">{{ visual: '画面', script: '台词', camera: '拍摄' }[field]}</span>
                            <textarea className="form-input" style={{ fontSize: 12, flex: 1 }} rows={2}
                              value={scene[field]}
                              onChange={e => setEditScript(s => {
                                const sb = [...(s!.storyboard || [])];
                                sb[idx] = { ...sb[idx], [field]: e.target.value };
                                return { ...s!, storyboard: sb };
                              })}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="script-section">
              <div className="script-section-title">📱 发布文案</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={4}
                value={editScript.caption_template || ''}
                onChange={e => setEditScript(s => ({ ...s!, caption_template: e.target.value }))}
              />
            </div>
            <div className="script-section">
              <div className="script-section-title">🏷️ 话题标签</div>
              <textarea className="form-input" style={{ fontSize: 13 }} rows={2}
                value={editScript.hashtag_suggestions?.join(' ') || ''}
                onChange={e => setEditScript(s => ({ ...s!, hashtag_suggestions: e.target.value.split(/\s+/).filter(Boolean) }))}
                placeholder="空格分隔，不需要加 #"
              />
            </div>
          </div>
        )}

        {script && !isEditing && (
          <div className="script-export-canvas" aria-hidden="true">
            <div ref={exportImageRef} className="script-export-long">
              <div className="script-export-topbar">
                <span className="script-export-topbar-badge">完整脚本</span>
                <span className="script-export-topbar-meta">第 {item.day_number} 天</span>
              </div>
              <div className="script-export-head">
                <div className="script-export-day">第 {item.day_number} 天内容策划</div>
                <h1 className="script-export-title">{item.title_direction}</h1>
                <p className="script-export-subtitle">用于客户预览的完整脚本长图，包含标题策略、开头钩子、分镜节奏与发布信息。</p>
              </div>

              <div className="script-export-hero-grid">
                <div className="script-export-metric">
                  <div className="script-export-metric-label">建议时长</div>
                  <div className="script-export-metric-value">{script.estimated_duration?.trim() || '按分镜节奏执行'}</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">分镜数量</div>
                  <div className="script-export-metric-value">{script.storyboard?.length || 0} 个场景</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">标题备选</div>
                  <div className="script-export-metric-value">{(script.title_options || []).filter(Boolean).length || 0} 条</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">适用阶段</div>
                  <div className="script-export-metric-value">客户确认版</div>
                </div>
              </div>

              <div className="script-export-main">
                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">01</div>
                    <div>
                      <div className="script-export-card-label">标题备选</div>
                      <div className="script-export-section-subtitle">先看传播入口，优先筛出最有点击欲望的一版标题。</div>
                    </div>
                  </div>
                  <div className="script-export-list">
                    {((script.title_options || []).filter(Boolean).length ? (script.title_options || []).filter(Boolean) : ['待补充标题']).map((title, titleIndex) => (
                      <div key={`title-${titleIndex}`} className="script-export-list-item">
                        {title}
                      </div>
                    ))}
                  </div>
                </section>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">02</div>
                    <div>
                      <div className="script-export-card-label">黄金3秒开头</div>
                      <div className="script-export-section-subtitle">第一句就要抓人，避免平铺直叙地自我介绍。</div>
                    </div>
                  </div>
                  <div className="script-export-copy">{script.hook_script?.trim() || '待补充开头钩子'}</div>
                </section>

                <div className="script-export-grid">
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">03</div>
                      <div>
                        <div className="script-export-card-label">建议时长</div>
                        <div className="script-export-section-subtitle">方便客户快速判断拍摄密度。</div>
                      </div>
                    </div>
                    <div className="script-export-copy is-compact">{script.estimated_duration?.trim() || '按分镜节奏执行'}</div>
                  </section>
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">04</div>
                      <div>
                        <div className="script-export-card-label">完整口播思路</div>
                        <div className="script-export-section-subtitle">整体表达主线，帮助客户先抓核心感觉。</div>
                      </div>
                    </div>
                    <div className="script-export-copy is-compact">
                      {script.full_narration?.trim() || '以分镜中的台词内容为主线推进'}
                    </div>
                  </section>
                </div>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">05</div>
                    <div>
                      <div className="script-export-card-label">分镜脚本</div>
                      <div className="script-export-section-subtitle">逐镜头拆清楚画面、台词和拍摄动作，方便直接进入执行。</div>
                    </div>
                  </div>
                  <div className="script-export-scenes">
                    {(script.storyboard?.length ? script.storyboard : [{
                      scene: 1,
                      duration: '',
                      visual: '待补充分镜画面',
                      script: '待补充分镜台词',
                      camera: '待补充拍摄方式',
                    }]).map((scene, index) => (
                      <section key={`scene-${scene.scene}-${index}`} className="script-export-scene-card">
                        <div className="script-export-scene-head">
                          <span className="script-export-scene-badge">Scene {scene.scene}</span>
                          <span className="script-export-scene-duration">{scene.duration || '时长待定'}</span>
                        </div>
                        <div className="script-export-scene-body">
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">画面</div>
                            <div className="script-export-scene-value">{scene.visual}</div>
                          </div>
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">台词</div>
                            <div className="script-export-scene-value">{scene.script}</div>
                          </div>
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">拍摄</div>
                            <div className="script-export-scene-value">{scene.camera}</div>
                          </div>
                        </div>
                      </section>
                    ))}
                  </div>
                </section>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">06</div>
                    <div>
                      <div className="script-export-card-label">发布文案</div>
                      <div className="script-export-section-subtitle">给客户直接看发布层表达，不只是拍摄层脚本。</div>
                    </div>
                  </div>
                  <div className="script-export-copy">{script.caption_template?.trim() || '待补充发布文案'}</div>
                </section>

                <div className="script-export-grid">
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">07</div>
                      <div>
                        <div className="script-export-card-label">话题标签</div>
                        <div className="script-export-section-subtitle">补足发布动作，方便直接带走使用。</div>
                      </div>
                    </div>
                    <div className="script-export-tags">
                      {((script.hashtag_suggestions || []).filter(Boolean).length ? (script.hashtag_suggestions || []).filter(Boolean) : ['待补充标签']).map((tag, tagIndex) => (
                        <span key={`tag-${tagIndex}`} className="script-export-tag">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </section>
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">08</div>
                      <div>
                        <div className="script-export-card-label">拍摄提醒</div>
                        <div className="script-export-section-subtitle">把执行注意点提前说透，减少反复确认。</div>
                      </div>
                    </div>
                    <div className="script-export-list is-compact">
                      {((script.filming_tips || []).filter(Boolean).length ? (script.filming_tips || []).filter(Boolean) : ['按分镜顺序执行，注意节奏和停顿']).map((tip, tipIndex) => (
                        <div key={`tip-${tipIndex}`} className="script-export-list-item is-compact">
                          {tip}
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              </div>

              <div className="script-export-footer">
                <span className="script-export-footer-mark">Douyin Manager</span>
                <span className="script-export-footer-text">此长图用于客户确认脚本方向，不替代现场拍摄微调。</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

function EditProjectModal({ project, onClose, onSaved }: {
  project: { id: string; client_name: string; industry: string; target_audience: string; unique_advantage?: string; ip_requirements: string; style_preference?: string; business_goal?: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<UpdatePlanningRequest>({
    client_name: project.client_name,
    industry: project.industry,
    target_audience: project.target_audience,
    unique_advantage: project.unique_advantage || '',
    ip_requirements: project.ip_requirements,
    style_preference: project.style_preference || '',
    business_goal: project.business_goal || '',
  });

  const mutation = useMutation({
    mutationFn: (data: UpdatePlanningRequest) => planningApi.update(project.id, data),
    onSuccess: onSaved,
  });

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal edit-project-modal animate-scale-in" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">编辑策划信息</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4 edit-project-modal-body" style={{ padding: '0 0 4px' }}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">客户/品牌名称 *</label>
              <input className="form-input" value={form.client_name || ''} onChange={e => setForm(f => ({ ...f, client_name: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">行业垂类 *</label>
              <input className="form-input" value={form.industry || ''} onChange={e => setForm(f => ({ ...f, industry: e.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">目标受众画像 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.target_audience || ''} onChange={e => setForm(f => ({ ...f, target_audience: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">独特优势/亮点</label>
            <input className="form-input" value={form.unique_advantage || ''} onChange={e => setForm(f => ({ ...f, unique_advantage: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">IP 定位需求 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.ip_requirements || ''} onChange={e => setForm(f => ({ ...f, ip_requirements: e.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">风格偏好</label>
              <input className="form-input" value={form.style_preference || ''} onChange={e => setForm(f => ({ ...f, style_preference: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">商业目标</label>
              <input className="form-input" value={form.business_goal || ''} onChange={e => setForm(f => ({ ...f, business_goal: e.target.value }))} />
            </div>
          </div>
          {mutation.isError && <div className="error-tip">{(mutation.error as Error).message}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={mutation.isPending}>取消</button>
          <button
            className="btn btn-primary"
            disabled={!form.client_name || !form.industry || !form.target_audience || !form.ip_requirements || mutation.isPending}
            onClick={() => mutation.mutate(form)}
          >
            <Save size={14} /> {mutation.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function EditPlanModal({ projectId, plan, onClose, onSaved }: {
  projectId: string;
  plan: NonNullable<import('../../api/client').AccountPlan>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const pos = plan.account_positioning;
  const strat = plan.content_strategy;

  const [form, setForm] = useState({
    core_identity: pos?.core_identity || '',
    bio_suggestion: pos?.bio_suggestion || '',
    personality_tags: pos?.personality_tags?.join('、') || '',
    target_audience_detail: pos?.target_audience_detail || '',
    differentiation: pos?.differentiation || '',
    user_value: pos?.user_value || '',
    follow_reason: pos?.follow_reason || '',
    content_pillars: pos?.content_pillars ? JSON.stringify(pos.content_pillars, null, 2) : '[]',
    primary_format: strat?.primary_format || '',
    posting_frequency: strat?.posting_frequency || '',
    best_posting_times: strat?.best_posting_times?.join('、') || '',
    content_tone: strat?.content_tone || '',
    stop_scroll_reason: strat?.stop_scroll_reason || '',
    interaction_trigger: strat?.interaction_trigger || '',
    hook_template: strat?.hook_template || '',
    cta_template: strat?.cta_template || '',
  });
  const [pillarsError, setPillarsError] = useState('');

  const mutation = useMutation({
    mutationFn: () => {
      let content_pillars;
      try {
        content_pillars = JSON.parse(form.content_pillars);
        setPillarsError('');
      } catch {
        setPillarsError('内容支柱 JSON 格式有误');
        throw new Error('内容支柱 JSON 格式有误');
      }
      const newPlan: import('../../api/client').AccountPlan = {
        ...plan,
        account_positioning: {
          core_identity: form.core_identity,
          bio_suggestion: form.bio_suggestion,
          personality_tags: form.personality_tags.split(/[、,，\s]+/).filter(Boolean),
          target_audience_detail: form.target_audience_detail,
          content_pillars,
          differentiation: form.differentiation,
          user_value: form.user_value,
          follow_reason: form.follow_reason,
        },
        content_strategy: {
          primary_format: form.primary_format,
          posting_frequency: form.posting_frequency,
          best_posting_times: form.best_posting_times.split(/[、,，\s]+/).filter(Boolean),
          content_tone: form.content_tone,
          stop_scroll_reason: form.stop_scroll_reason,
          interaction_trigger: form.interaction_trigger,
          hook_template: form.hook_template,
          cta_template: form.cta_template,
        },
      };
      return planningApi.update(projectId, { account_plan: newPlan });
    },
    onSuccess: onSaved,
  });

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal edit-plan-modal animate-scale-in" style={{ maxWidth: 640 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">编辑账号定位方案</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4 edit-plan-modal-body" style={{ padding: '0 0 4px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>账号定位</div>
          <div className="form-group">
            <label className="form-label">核心定位 Slogan</label>
            <input className="form-input" value={form.core_identity} onChange={e => setForm(f => ({ ...f, core_identity: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">主页简介建议</label>
            <textarea className="form-input form-textarea" rows={2} value={form.bio_suggestion} onChange={e => setForm(f => ({ ...f, bio_suggestion: e.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">人设标签 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号或逗号分隔）</span></label>
              <input className="form-input" value={form.personality_tags} onChange={e => setForm(f => ({ ...f, personality_tags: e.target.value }))} placeholder="如：专业、亲切、幽默" />
            </div>
            <div className="form-group">
              <label className="form-label">目标受众细化</label>
              <input className="form-input" value={form.target_audience_detail} onChange={e => setForm(f => ({ ...f, target_audience_detail: e.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">差异化优势</label>
            <input className="form-input" value={form.differentiation} onChange={e => setForm(f => ({ ...f, differentiation: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">用户持续获得什么</label>
            <textarea className="form-input form-textarea" rows={3} value={form.user_value} onChange={e => setForm(f => ({ ...f, user_value: e.target.value }))} placeholder="用户持续看下去，能稳定获得什么具体判断、方法或避坑价值" />
          </div>
          <div className="form-group">
            <label className="form-label">用户为什么会关注</label>
            <textarea className="form-input form-textarea" rows={3} value={form.follow_reason} onChange={e => setForm(f => ({ ...f, follow_reason: e.target.value }))} placeholder="为什么不是看完就走，而是愿意继续关注你后续内容" />
          </div>
          <div className="form-group">
            <label className="form-label">内容支柱 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 name/ratio/description）</span></label>
            <textarea className="form-input form-textarea" rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }}
              value={form.content_pillars}
              onChange={e => { setForm(f => ({ ...f, content_pillars: e.target.value })); setPillarsError(''); }}
            />
            {pillarsError && <div className="error-tip" style={{ marginTop: 4 }}>{pillarsError}</div>}
          </div>

          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>内容策略</div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">内容形式</label>
              <input className="form-input" value={form.primary_format} onChange={e => setForm(f => ({ ...f, primary_format: e.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">发布频率</label>
              <input className="form-input" value={form.posting_frequency} onChange={e => setForm(f => ({ ...f, posting_frequency: e.target.value }))} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">最佳发布时间 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号分隔）</span></label>
              <input className="form-input" value={form.best_posting_times} onChange={e => setForm(f => ({ ...f, best_posting_times: e.target.value }))} placeholder="如：18:00、21:00" />
            </div>
            <div className="form-group">
              <label className="form-label">内容基调</label>
              <input className="form-input" value={form.content_tone} onChange={e => setForm(f => ({ ...f, content_tone: e.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">用户为什么会停下来继续看</label>
            <textarea className="form-input form-textarea" rows={3} value={form.stop_scroll_reason} onChange={e => setForm(f => ({ ...f, stop_scroll_reason: e.target.value }))} placeholder="陌生用户刷到时，具体会被什么信息回报、冲突或判断点留下来" />
          </div>
          <div className="form-group">
            <label className="form-label">互动触发点</label>
            <textarea className="form-input form-textarea" rows={3} value={form.interaction_trigger} onChange={e => setForm(f => ({ ...f, interaction_trigger: e.target.value }))} placeholder="什么会让用户愿意评论、收藏、私信，而不是只看不动" />
          </div>
          <div className="form-group">
            <label className="form-label">钩子模板</label>
            <input className="form-input" value={form.hook_template} onChange={e => setForm(f => ({ ...f, hook_template: e.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">CTA 模板</label>
            <input className="form-input" value={form.cta_template} onChange={e => setForm(f => ({ ...f, cta_template: e.target.value }))} />
          </div>
          {mutation.isError && <div className="error-tip">{(mutation.error as Error).message}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={mutation.isPending}>取消</button>
          <button className="btn btn-primary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
            <Save size={14} /> {mutation.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function PerformanceModal({
  projectId,
  contentItems,
  editing,
  onClose,
  onSaved,
}: {
  projectId: string;
  contentItems: ContentItem[];
  editing: ContentPerformance | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<ContentPerformanceCreateRequest>({
    content_item_id: editing?.content_item_id || null,
    title: editing?.title || '',
    platform: editing?.platform || 'douyin',
    publish_date: editing?.publish_date || null,
    video_url: editing?.video_url || null,
    views: editing?.views || 0,
    bounce_2s_rate: editing?.bounce_2s_rate ?? null,
    completion_5s_rate: editing?.completion_5s_rate ?? null,
    completion_rate: editing?.completion_rate ?? null,
    likes: editing?.likes || 0,
    comments: editing?.comments || 0,
    shares: editing?.shares || 0,
    conversions: editing?.conversions || 0,
    notes: editing?.notes || '',
  });

  const contentItemMap = useMemo(
    () => new Map(contentItems.map((item) => [item.id, item])),
    [contentItems]
  );
  const selectedContentItem = form.content_item_id ? contentItemMap.get(form.content_item_id) || null : null;

  const parseMutation = useMutation({
    mutationFn: async () => {
      const url = (form.video_url || '').trim();
      if (!url) throw new Error('请先填写作品链接');
      const parsed = await downloadApi.parse(url);
      return parsed;
    },
    onSuccess: (parsed) => {
      const publishDate = parsed.published_at ? parsed.published_at.split('T')[0] : null;
      setForm((prev) => ({
        ...prev,
        title: (parsed.title || prev.title || '').trim(),
        platform: (parsed.platform || prev.platform || 'douyin').trim(),
        publish_date: publishDate || prev.publish_date || null,
        views: typeof parsed.view_count === 'number' ? parsed.view_count : (prev.views ?? 0),
        likes: typeof parsed.like_count === 'number' ? parsed.like_count : (prev.likes ?? 0),
        comments: typeof parsed.comment_count === 'number' ? parsed.comment_count : (prev.comments ?? 0),
        shares: typeof parsed.share_count === 'number' ? parsed.share_count : (prev.shares ?? 0),
      }));
    },
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const normalizedUrl = (form.video_url || '').trim();
      const payload: ContentPerformanceCreateRequest = {
        ...form,
        publish_date: form.publish_date || null,
        video_url: normalizedUrl || null,
        notes: form.notes?.trim() || null,
        title: form.title.trim(),
      };
      if (!payload.video_url) throw new Error('请填写作品链接');
      if (!payload.title) throw new Error('请填写内容标题，或先关联策划条目/抓取链接信息');
      if (editing) {
        return planningApi.updatePerformance(projectId, editing.id, payload);
      }
      return planningApi.createPerformance(projectId, payload);
    },
    onSuccess: onSaved,
  });

  const updateRate = (key: 'bounce_2s_rate' | 'completion_5s_rate' | 'completion_rate', value: string) => {
    const num = value === '' ? 0 : Number(value);
    setForm((prev) => ({ ...prev, [key]: value === '' ? null : (Number.isFinite(num) ? num : null) }));
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal animate-scale-in" style={{ maxWidth: 640 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{editing ? '编辑回流数据' : '新增回流数据'}</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4">
          <div className="form-group">
            <label className="form-label">作品链接 *</label>
            <div className="flex items-center gap-2">
              <input
                className="form-input"
                value={form.video_url || ''}
                placeholder="粘贴抖音视频链接，可抓取基础信息"
                onChange={(e) => {
                  const value = e.target.value;
                  setForm((f) => ({ ...f, video_url: value }));
                }}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => parseMutation.mutate()}
                disabled={parseMutation.isPending || !(form.video_url || '').trim()}
              >
                {parseMutation.isPending ? '抓取中...' : '抓取信息'}
              </button>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">关联策划条目</label>
            <CustomSelect
              triggerClassName="form-input"
              className="project-detail-select"
              value={form.content_item_id || ''}
              options={[
                { value: '', label: '不关联，作为独立回流记录' },
                ...contentItems.map((item) => ({
                  value: item.id,
                  label: getContentItemLabel(item),
                })),
              ]}
              onChange={(value) => {
                const nextId = value || null;
                setForm((prev) => {
                  const nextItem = nextId ? contentItemMap.get(nextId) || null : null;
                  const nextTitle = !prev.title.trim() && nextItem ? nextItem.title_direction : prev.title;
                  return {
                    ...prev,
                    content_item_id: nextId,
                    title: nextTitle,
                  };
                });
              }}
            />
            {selectedContentItem && (
              <div className="form-hint">已关联到 {getContentItemLabel(selectedContentItem)}</div>
            )}
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">内容标题</label>
              <input
                className="form-input"
                value={form.title || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">发布日期</label>
              <input
                type="date"
                className="form-input"
                value={form.publish_date || ''}
                onChange={(e) => setForm((prev) => ({ ...prev, publish_date: e.target.value || null }))}
              />
            </div>
          </div>

          <div className="grid-4">
            <div className="form-group">
              <label className="form-label">播放</label>
              <input
                type="number"
                min={0}
                className="form-input"
                value={form.views ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, views: Math.max(0, Number(e.target.value || 0)) }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">点赞</label>
              <input
                type="number"
                min={0}
                className="form-input"
                value={form.likes ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, likes: Math.max(0, Number(e.target.value || 0)) }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">评论</label>
              <input
                type="number"
                min={0}
                className="form-input"
                value={form.comments ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, comments: Math.max(0, Number(e.target.value || 0)) }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">转发</label>
              <input
                type="number"
                min={0}
                className="form-input"
                value={form.shares ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, shares: Math.max(0, Number(e.target.value || 0)) }))}
              />
            </div>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">转化数</label>
              <input
                type="number"
                min={0}
                className="form-input"
                value={form.conversions ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, conversions: Math.max(0, Number(e.target.value || 0)) }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">发布平台</label>
              <input
                className="form-input"
                value={form.platform || 'douyin'}
                onChange={(e) => setForm((prev) => ({ ...prev, platform: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid-3">
            <div className="form-group">
              <label className="form-label">2秒跳出率(%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                className="form-input"
                value={form.bounce_2s_rate ?? ''}
                onChange={(e) => {
                  updateRate('bounce_2s_rate', e.target.value);
                }}
              />
            </div>
            <div className="form-group">
              <label className="form-label">5秒完播率(%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                className="form-input"
                value={form.completion_5s_rate ?? ''}
                onChange={(e) => {
                  updateRate('completion_5s_rate', e.target.value);
                }}
              />
            </div>
            <div className="form-group">
              <label className="form-label">整体完播率(%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                className="form-input"
                value={form.completion_rate ?? ''}
                onChange={(e) => {
                  updateRate('completion_rate', e.target.value);
                }}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">复盘备注</label>
            <textarea
              className="form-input form-textarea"
              rows={3}
              value={form.notes || ''}
              placeholder="例如：开头前三秒用强对比，评论区多问价格，门店成交来自直播间导流"
              onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
            />
          </div>

          {parseMutation.isError && <div className="error-tip">{(parseMutation.error as Error).message}</div>}
          {mutation.isError && <div className="error-tip">{(mutation.error as Error).message}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>取消</button>
          <button className="btn btn-primary" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <Save size={14} /> {mutation.isPending ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [activeItem, setActiveItem] = useState<ContentItem | null>(null);
  const [showFullPlan, setShowFullPlan] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title_direction: '', content_type: '' });
  const [showEditProject, setShowEditProject] = useState(false);
  const [showEditPlan, setShowEditPlan] = useState(false);
  const [isSelectingRegenerateDays, setIsSelectingRegenerateDays] = useState(false);
  const [regenerateSelectedDays, setRegenerateSelectedDays] = useState<number[]>([]);
  const [showPerformanceModal, setShowPerformanceModal] = useState(false);
  const [editingPerformance, setEditingPerformance] = useState<ContentPerformance | null>(null);
  const [calendarFilter, setCalendarFilter] = useState<string>('all');

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: { title_direction: string; content_type: string } }) =>
      planningApi.updateContentItem(itemId, data),
    onSuccess: () => {
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => planningApi.get(id!),
    // 保持轻轮询，确保刷新/重开页面后仍可追踪脚本生成状态
    refetchInterval: 5000,
  });
  const { data: bloggers = [] } = useQuery({
    queryKey: ['bloggers'],
    queryFn: () => bloggerApi.list(),
  });

  const { data: scriptTaskPage } = useQuery({
    queryKey: ['content-script-tasks', id],
    queryFn: () =>
      taskApi.list({
        entity_type: 'content_item',
        task_type: 'planning_script_generate',
        limit: 200,
      }),
    enabled: Boolean(id),
    refetchInterval: 3000,
  });

  const { data: projectTaskPage } = useQuery({
    queryKey: ['project-planning-tasks', id],
    queryFn: () =>
      taskApi.list({
        entity_type: 'planning_project',
        entity_id: id!,
        limit: 50,
      }),
    enabled: Boolean(id),
    refetchInterval: 3000,
  });

  const scriptTaskMap = useMemo(() => {
    const map = new Map<string, TaskCenterItem>();
    const tasks = scriptTaskPage?.items || [];
    for (const task of tasks) {
      const prev = map.get(task.entity_id);
      if (!prev || toBackendTimestamp(task.updated_at) >= toBackendTimestamp(prev.updated_at)) {
        map.set(task.entity_id, task);
      }
    }
    return map;
  }, [scriptTaskPage]);

  const { data: performanceList = [] } = useQuery({
    queryKey: ['project-performance', id],
    queryFn: () => planningApi.listPerformance(id!),
    enabled: Boolean(id),
  });

  const { data: performanceSummary } = useQuery({
    queryKey: ['project-performance-summary', id],
    queryFn: () => planningApi.getPerformanceSummary(id!),
    enabled: Boolean(id),
  });

  const latestPlanningTaskByType = useMemo(() => {
    const map = new Map<string, TaskCenterItem>();
    for (const task of projectTaskPage?.items || []) {
      const previous = map.get(task.task_type);
      if (!previous || toBackendTimestamp(task.updated_at) >= toBackendTimestamp(previous.updated_at)) {
        map.set(task.task_type, task);
      }
    }
    return map;
  }, [projectTaskPage]);

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
      setIsSelectingRegenerateDays(false);
      setRegenerateSelectedDays([]);
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

  const plan = project?.account_plan;
  const currentStage: ProjectStage = project ? inferProjectStage(project) : 'draft';
  const positioning = plan?.account_positioning;
  const strategy = plan?.content_strategy;
  const hasStrategy = Boolean(positioning || strategy);
  const hasCalendar = Boolean((project?.content_calendar || []).length > 0 || (project?.content_items || []).length > 0);
  const performanceRecap = plan?.performance_recap;
  const nextTopicBatch = plan?.next_topic_batch;
  const latestStrategyTask = latestPlanningTaskByType.get('planning_generate') || null;
  const latestCalendarTask = latestPlanningTaskByType.get('planning_calendar') || null;
  const pendingCalendarRegeneration = useMemo(
    () => buildPendingCalendarRegeneration(latestCalendarTask),
    [latestCalendarTask],
  );
  const contentItemMap = new Map((project?.content_items || []).map((item) => [item.id, item]));
  const calendarMetaByDay = new Map<number, ContentCalendarItem>(
    (project?.content_calendar || [])
      .filter((item): item is ContentCalendarItem => Boolean(item && typeof item.day === 'number'))
      .map((item) => [item.day, item]),
  );
  const calendarDisplayItems: CalendarDisplayItem[] = (project?.content_items || [])
    .map((item) => ({
      ...item,
      calendarMeta: calendarMetaByDay.get(item.day_number) || null,
    }))
    .sort((a, b) => a.day_number - b.day_number);
  const visibleCalendarItems = useMemo(() => {
    if (!pendingCalendarRegeneration) return calendarDisplayItems;
    const currentByDay = new Map(calendarDisplayItems.map((item) => [item.day_number, item]));
    const mergedItems = [...calendarDisplayItems];
    for (const dayNumber of pendingCalendarRegeneration.dayNumbers) {
      if (currentByDay.has(dayNumber)) continue;
      const snapshot = pendingCalendarRegeneration.snapshotsByDay[dayNumber];
      if (snapshot) mergedItems.push(snapshot);
    }
    return mergedItems.sort((a, b) => a.day_number - b.day_number);
  }, [calendarDisplayItems, pendingCalendarRegeneration]);
  const pendingRegenerationDaySet = useMemo(
    () => new Set(pendingCalendarRegeneration?.dayNumbers || []),
    [pendingCalendarRegeneration],
  );
  const scheduleGroupEntries = Array.from(
    visibleCalendarItems.reduce((map, item) => {
      const group = getCalendarScheduleMeta(item).scheduleGroup;
      if (!group) return map;
      map.set(group, (map.get(group) || 0) + 1);
      return map;
    }, new Map<string, number>()),
  );
  const filteredCalendarItems = visibleCalendarItems.filter((item) => {
    if (calendarFilter === 'all') return true;
    if (calendarFilter.startsWith(SCHEDULE_GROUP_FILTER_PREFIX)) {
      return getCalendarScheduleMeta(item).scheduleGroup === calendarFilter.slice(SCHEDULE_GROUP_FILTER_PREFIX.length);
    }
    return true;
  });
  const linkedContentItemIds = new Set(
    performanceList.map((row) => row.content_item_id).filter((value): value is string => Boolean(value))
  );
  const pendingContentItems = (project?.content_items || []).filter((item) => !linkedContentItemIds.has(item.id));
  const bloggerNameMap = new Map(bloggers.map((blogger) => [blogger.id, blogger.nickname]));
  const referenceNames = (project?.reference_blogger_ids || [])
    .map((bloggerId) => bloggerNameMap.get(bloggerId))
    .filter((name): name is string => Boolean(name));
  const referenceScopeItems = [
    `账号定位会参考 ${referenceNames.join('、')} 的人设切入点、受众表达方式和内容支柱拆法，但会优先贴合你当前账号的行业、目标受众和商业目标。`,
    '30 天内容日历会参考这些 IP 里更稳定的选题方向、内容结构和更新节奏，用来辅助规划每天拍什么，不会直接照搬某一条内容。',
    '后续生成单条脚本时，也会继续参考这些 IP 的开头节奏、表达习惯和镜头组织方式，但脚本会按你当前项目的定位重新写。',
    '如果后面你更换或减少参考 IP，重新生成策划和日历后，下面这套方案也会跟着变化。',
  ];
  const allCalendarDays = visibleCalendarItems.map((item) => item.day_number);
  const preservedDayCount = Math.max(0, visibleCalendarItems.length - regenerateSelectedDays.length);
  const displayCalendarItems = isSelectingRegenerateDays ? visibleCalendarItems : filteredCalendarItems;
  const isStrategyRegenerating = Boolean(hasStrategy && (currentStage === 'strategy_generating' || isPendingTask(latestStrategyTask)));

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

  const toggleRegenerateDay = (dayNumber: number) => {
    setRegenerateSelectedDays((prev) =>
      prev.includes(dayNumber) ? prev.filter((day) => day !== dayNumber) : [...prev, dayNumber].sort((a, b) => a - b)
    );
  };

  const startInlineRegenerateSelection = () => {
    setCalendarFilter('all');
    setEditingId(null);
    setRegenerateSelectedDays([]);
    setIsSelectingRegenerateDays(true);
  };

  const cancelInlineRegenerateSelection = () => {
    setIsSelectingRegenerateDays(false);
    setRegenerateSelectedDays([]);
  };

  const submitSelectedRegeneration = () => {
    if (calendarDisplayItems.length > 0 && regenerateSelectedDays.length === 0) {
      notifyInfo('至少勾选 1 条需要重生成的内容');
      return;
    }
    setCalendarFilter('all');
    setActiveItem(null);
    regenerateCalendarMutation.mutate(regenerateSelectedDays);
  };

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
                setCalendarFilter('all');
                setActiveItem(null);
                regenerateCalendarMutation.mutate([]);
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

      {/* 30天内容日历 */}
      {(hasStrategy && (hasCalendar || currentStage === 'calendar_generating')) && (
        <div className="detail-calendar-wrap">
          <div className="detail-calendar-head">
            <div className="detail-calendar-title-wrap">
              <Calendar size={18} className="detail-calendar-icon" />
              <h2 className="detail-calendar-title">30天内容日历</h2>
              {calendarDisplayItems.length > 0 && (
                <span className="badge badge-purple">{calendarDisplayItems.length} 条</span>
              )}
              {calendarFilter !== 'all' && (
                <span className="badge badge-blue">{filteredCalendarItems.length} 条已筛选</span>
              )}
            </div>
            {currentStage !== 'strategy_generating' && currentStage !== 'calendar_generating' && hasCalendar && (
              <div className="detail-calendar-actions">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => {
                    setCalendarFilter('all');
                    setActiveItem(null);
                    regenerateCalendarMutation.mutate([]);
                  }}
                  disabled={regenerateCalendarMutation.isPending || isSelectingRegenerateDays}
                >
                  <RefreshCw size={13} /> {regenerateCalendarMutation.isPending && !isSelectingRegenerateDays ? '生成中...' : '重新生成日历'}
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={startInlineRegenerateSelection}
                  disabled={regenerateCalendarMutation.isPending || isSelectingRegenerateDays}
                >
                  <RefreshCw size={13} /> 选中重新生成
                </button>
              </div>
            )}
          </div>

          {currentStage === 'calendar_generating' && !hasCalendar ? (
            <div className="card detail-calendar-empty">
              <Loader2 size={32} className="spin-icon detail-calendar-empty-icon" />
              <div className="detail-calendar-empty-text">正在为您深度规划每天的内容方向与形式...</div>
            </div>
          ) : (
            <>
            {calendarDisplayItems.length > 0 && (
              <div className="calendar-summary-row">
                <button
                  type="button"
                  className={`calendar-summary-pill ${calendarFilter === 'all' ? 'is-active' : ''}`}
                  onClick={() => setCalendarFilter('all')}
                  disabled={isSelectingRegenerateDays}
                >
                  <span className="calendar-summary-label">全部</span>
                  <strong>{calendarDisplayItems.length}</strong>
                </button>
                {scheduleGroupEntries.map(([group, count]) => {
                  const filterKey = `${SCHEDULE_GROUP_FILTER_PREFIX}${group}`;
                  return (
                    <button
                      key={group}
                      type="button"
                      className={`calendar-summary-pill ${calendarFilter === filterKey ? 'is-active' : ''}`}
                      onClick={() => setCalendarFilter(filterKey)}
                      disabled={isSelectingRegenerateDays}
                    >
                      <span className="calendar-summary-label">{group}</span>
                      <strong>{count}</strong>
                    </button>
                  );
                })}
              </div>
            )}
            {isSelectingRegenerateDays && (
              <div className="calendar-inline-regenerate-bar">
                <div className="calendar-inline-regenerate-copy">
                  <div className="calendar-inline-regenerate-title">选中需要重生成的日期块</div>
                  <div className="calendar-inline-regenerate-text">
                    已选 {regenerateSelectedDays.length} 条，保留 {preservedDayCount} 条。勾选的会重写，没勾选的保持不动。
                  </div>
                </div>
                <div className="calendar-inline-regenerate-actions">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setRegenerateSelectedDays(allCalendarDays)}
                    disabled={regenerateCalendarMutation.isPending}
                  >
                    全选
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setRegenerateSelectedDays([])}
                    disabled={regenerateCalendarMutation.isPending}
                  >
                    清空
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={cancelInlineRegenerateSelection}
                    disabled={regenerateCalendarMutation.isPending}
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={submitSelectedRegeneration}
                    disabled={regenerateCalendarMutation.isPending}
                  >
                    {regenerateCalendarMutation.isPending ? (
                      <><Loader2 size={14} className="spin-icon" /> 生成中...</>
                    ) : (
                      <><RefreshCw size={14} /> 确认重生成</>
                    )}
                  </button>
                </div>
              </div>
            )}
            {regenerateCalendarMutation.isError && (
              <div className="error-tip">{(regenerateCalendarMutation.error as Error).message}</div>
            )}
            {displayCalendarItems.length > 0 ? (
            <div className="calendar-grid">
            {displayCalendarItems.map(item => {
                const scheduleMeta = getCalendarScheduleMeta(item);
                const isSelectedForRegenerate = regenerateSelectedDays.includes(item.day_number);
                const isPendingRegenerate = pendingRegenerationDaySet.has(item.day_number);
                return (
                <div
                  key={item.id}
                  className={`calendar-item ${item.is_script_generated ? 'calendar-item-done' : ''} ${editingId === item.id ? 'calendar-item-editing' : ''} ${isSelectingRegenerateDays ? 'calendar-item-selecting' : ''} ${isSelectedForRegenerate ? 'calendar-item-selected' : ''} ${isPendingRegenerate ? 'calendar-item-regenerating' : ''}`}
                  onClick={() => {
                    if (editingId === item.id) return;
                    if (isPendingRegenerate) return;
                    if (isSelectingRegenerateDays) {
                      toggleRegenerateDay(item.day_number);
                      return;
                    }
                    setActiveItem(item);
                  }}
                >
                  <div className="calendar-item-body">
                    {editingId === item.id ? (
                      <div className="calendar-edit-form" onClick={e => e.stopPropagation()}>
                        <input
                          className="form-input calendar-edit-input"
                          value={editForm.title_direction}
                          onChange={e => setEditForm(f => ({ ...f, title_direction: e.target.value }))}
                          placeholder="内容方向"
                        />
                        <input
                          className="form-input calendar-edit-input"
                          value={editForm.content_type}
                          onChange={e => setEditForm(f => ({ ...f, content_type: e.target.value }))}
                          placeholder="内容类型"
                        />
                        <div className="flex gap-2 calendar-edit-actions">
                          <button
                            className="btn btn-primary btn-sm calendar-edit-save"
                            disabled={updateItemMutation.isPending}
                            onClick={() => updateItemMutation.mutate({ itemId: item.id, data: editForm })}
                          >
                            <Save size={12} /> {updateItemMutation.isPending ? '保存中...' : '保存'}
                          </button>
                          <button className="btn btn-ghost btn-sm" onClick={() => setEditingId(null)}>
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="calendar-day-row">
                          <span className="calendar-day">Day {item.day_number}</span>
                          {isSelectingRegenerateDays ? (
                            <span className={`calendar-select-indicator ${isSelectedForRegenerate ? 'is-selected' : ''}`}>
                              {isSelectedForRegenerate ? '已选' : '选择'}
                            </span>
                          ) : (
                            <button
                              className="btn btn-icon btn-ghost calendar-edit-btn"
                              style={{ width: 22, height: 22, minWidth: 22 }}
                              onClick={e => {
                                e.stopPropagation();
                                setEditForm({ title_direction: item.title_direction, content_type: item.content_type || '' });
                                setEditingId(item.id);
                              }}
                            >
                              <Pencil size={11} />
                            </button>
                          )}
                        </div>
                        <div className="calendar-title">{item.title_direction}</div>
                        <div className="calendar-tags">
                          <span className="badge badge-purple calendar-production-badge">
                            {scheduleMeta.shootFormat}
                          </span>
                        </div>
                        <div className="calendar-meta">
                          <span className="badge badge-purple calendar-type-badge">{item.content_type || '待定'}</span>
                          {item.is_script_generated ? (
                            <span className="script-done-label">✓ 已生成</span>
                          ) : (scriptTaskMap.get(item.id)?.status === 'queued' || scriptTaskMap.get(item.id)?.status === 'running') ? (
                            <span className="script-gen-label">生成中</span>
                          ) : scriptTaskMap.get(item.id)?.status === 'failed' ? (
                            <span className="script-gen-label">生成失败</span>
                          ) : (
                            <span className="script-gen-label">待生成</span>
                          )}
                        </div>
                        <div className="calendar-extra-line">
                          <span className="calendar-extra-label">出镜要求</span>
                          <span className="calendar-extra-value">{scheduleMeta.talentRequirement}</span>
                        </div>
                        <div className="calendar-extra-line">
                          <span className="calendar-extra-label">拍摄场景</span>
                          <span className="calendar-extra-value">{scheduleMeta.shootScene}</span>
                        </div>
                        <div className="calendar-extra-line">
                          <span className="calendar-extra-label">准备成本</span>
                          <span className="calendar-extra-value">{scheduleMeta.prepRequirement}</span>
                        </div>
                        <div className="calendar-extra-line">
                          <span className="calendar-extra-label">排期分组</span>
                          <span className="calendar-extra-value">{scheduleMeta.scheduleGroup}</span>
                        </div>
                        {item.calendarMeta?.replacement_hint ? (
                          <div className="calendar-extra-line calendar-extra-note">
                            <span className="calendar-extra-label">替换建议</span>
                            <span className="calendar-extra-value">{item.calendarMeta.replacement_hint}</span>
                          </div>
                        ) : null}
                      </>
                    )}
                  </div>
                  {isPendingRegenerate && (
                    <div className="calendar-regenerate-overlay">
                      <span className="calendar-regenerate-overlay-badge">
                        <Loader2 size={14} className="spin-icon" /> 重新生成中
                      </span>
                    </div>
                  )}
                </div>
              )})}
          </div>
            ) : (
              <div className="card detail-calendar-empty">
                <div className="detail-calendar-empty-text">当前筛选条件下没有匹配的日期块</div>
                <button className="btn btn-ghost btn-sm" onClick={() => setCalendarFilter('all')}>
                  清除筛选
                </button>
              </div>
            )}
          </>
          )}
        </div>
      )}

      <div className="card detail-section performance-section">
        <div className="detail-section-head">
          <h2 className="section-title detail-section-title flex items-center gap-2">
            <TrendingUp size={18} /> 发布后数据回流
          </h2>
          <div className="performance-head-actions">
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => generatePerformanceRecapMutation.mutate()}
              disabled={generatePerformanceRecapMutation.isPending || performanceList.length === 0}
            >
              <Sparkles size={13} /> {generatePerformanceRecapMutation.isPending ? '复盘中...' : 'AI 自动复盘'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                setEditingPerformance(null);
                setShowPerformanceModal(true);
              }}
            >
              <Plus size={13} /> 新增数据
            </button>
          </div>
        </div>

        <div className="performance-overview">
          <div className="performance-kpis">
            <div className="performance-kpi">
              <span>已回流 / 计划内容</span>
              <strong>
                {performanceSummary ? `${performanceSummary.total_items}/${performanceSummary.planned_content_count}` : `0/${project.content_items?.length || 0}`}
              </strong>
              <em>{formatMetricPercent(performanceSummary?.coverage_rate)}</em>
            </div>
            <div className="performance-kpi">
              <span>总播放</span>
              <strong>{formatMetricNumber(performanceSummary?.total_views)}</strong>
              <em>{formatMetricNumber(performanceSummary?.total_likes)} 点赞</em>
            </div>
            <div className="performance-kpi">
              <span>平均互动率</span>
              <strong>{formatMetricPercent(performanceSummary?.avg_engagement_rate)}</strong>
              <em>{formatMetricNumber((performanceSummary?.total_comments || 0) + (performanceSummary?.total_shares || 0))} 评论+转发</em>
            </div>
            <div className="performance-kpi">
              <span>平均 5 秒完播率</span>
              <strong>{formatMetricPercent(performanceSummary?.avg_completion_5s_rate)}</strong>
              <em>整体完播率 {formatMetricPercent(performanceSummary?.avg_completion_rate)}</em>
            </div>
            <div className="performance-kpi">
              <span>总转化</span>
              <strong>{formatMetricNumber(performanceSummary?.total_conversions)}</strong>
              <em>平均转化率 {formatMetricPercent(performanceSummary?.avg_conversion_rate)}</em>
            </div>
            <div className="performance-kpi">
              <span>待补回流</span>
              <strong>{formatMetricNumber(pendingContentItems.length)}</strong>
              <em>{pendingContentItems[0] ? getContentItemLabel(pendingContentItems[0]) : '当前已全部覆盖'}</em>
            </div>
          </div>

          {performanceSummary?.insights?.length ? (
            <div className="performance-insights">
              {performanceSummary.insights.map((insight) => (
                <div key={`${insight.title}-${insight.body}`} className={`performance-insight performance-insight-${insight.tone}`}>
                  <div className="performance-insight-title">{insight.title}</div>
                  <p>{insight.body}</p>
                </div>
              ))}
            </div>
          ) : null}

          <div className="performance-highlights">
            <div className="performance-highlight">
              <span>最高播放</span>
              <strong>{performanceSummary?.best_view_item?.title || '暂无数据'}</strong>
              <em>{getPerformanceHighlightMeta(performanceSummary?.best_view_item, 'views')}</em>
            </div>
            <div className="performance-highlight">
              <span>最佳完播</span>
              <strong>{performanceSummary?.best_completion_item?.title || '暂无数据'}</strong>
              <em>{getPerformanceHighlightMeta(performanceSummary?.best_completion_item, 'completion')}</em>
            </div>
            <div className="performance-highlight">
              <span>最佳互动</span>
              <strong>{performanceSummary?.best_engagement_item?.title || '暂无数据'}</strong>
              <em>{getPerformanceHighlightMeta(performanceSummary?.best_engagement_item, 'engagement')}</em>
            </div>
            <div className="performance-highlight">
              <span>最佳转化</span>
              <strong>{performanceSummary?.best_conversion_item?.title || '暂无数据'}</strong>
              <em>{getPerformanceHighlightMeta(performanceSummary?.best_conversion_item, 'conversion')}</em>
            </div>
          </div>
        </div>

        <div className="performance-recap-card">
          <div className="performance-recap-head">
            <div>
              <div className="performance-recap-eyebrow">AI 复盘</div>
              <h3>下一轮内容建议</h3>
            </div>
            <div className="performance-recap-side">
              <div className="performance-recap-meta">
                {performanceRecap ? `更新于 ${formatDateTime(performanceRecap.generated_at)}` : '录入回流后可一键生成'}
              </div>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => generateNextTopicBatchMutation.mutate()}
                disabled={generateNextTopicBatchMutation.isPending || !performanceRecap}
              >
                <Sparkles size={13} /> {generateNextTopicBatchMutation.isPending ? '生成中...' : '下一批10条选题'}
              </button>
            </div>
          </div>

          {generatePerformanceRecapMutation.isError && (
            <div className="error-tip" style={{ marginTop: 12 }}>
              {(generatePerformanceRecapMutation.error as Error).message}
            </div>
          )}
          {generateNextTopicBatchMutation.isError && (
            <div className="error-tip" style={{ marginTop: 12 }}>
              {(generateNextTopicBatchMutation.error as Error).message}
            </div>
          )}
          {importNextTopicBatchItemMutation.isError && (
            <div className="error-tip" style={{ marginTop: 12 }}>
              {(importNextTopicBatchItemMutation.error as Error).message}
            </div>
          )}

          {!performanceRecap ? (
            <div className="performance-recap-empty">
              {performanceList.length === 0
                ? '先录入至少 1 条回流数据，再生成 AI 自动复盘。'
                : '已经有回流数据了，可以点击上方“AI 自动复盘”生成下一轮选题和优化建议。'}
            </div>
          ) : (
            <div className="performance-recap-body">
              <p className="performance-recap-summary">{performanceRecap.overall_summary}</p>

              <div className="performance-recap-grid">
                <div className="performance-recap-block">
                  <span>继续放大</span>
                  <ul>
                    {performanceRecap.winning_patterns.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
                <div className="performance-recap-block">
                  <span>优先优化</span>
                  <ul>
                    {performanceRecap.optimization_focus.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
                <div className="performance-recap-block">
                  <span>风险提醒</span>
                  <ul>
                    {performanceRecap.risk_alerts.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
                <div className="performance-recap-block">
                  <span>下周动作</span>
                  <ul>
                    {performanceRecap.next_actions.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
                <div className="performance-recap-block performance-recap-block-wide">
                  <span>下一批选题方向</span>
                  <ul>
                    {performanceRecap.next_topic_angles.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="performance-topic-batch-card">
          <div className="performance-topic-batch-head">
            <div>
              <div className="performance-recap-eyebrow">选题批次</div>
              <h3>基于复盘的下一批 10 条</h3>
            </div>
            <div className="performance-recap-meta">
              {nextTopicBatch ? `更新于 ${formatDateTime(nextTopicBatch.generated_at)}` : '先生成 AI 复盘，再生成这一批选题'}
            </div>
          </div>

          {!nextTopicBatch ? (
            <div className="performance-recap-empty">
              {performanceRecap
                ? '可以点击上方“下一批10条选题”，快速生成一组更适合继续试跑的选题。'
                : '这一批选题会自动参考 AI 复盘中的有效模式、优化重点和风险提醒。'}
            </div>
          ) : (
            <div className="performance-topic-batch-body">
              <p className="performance-recap-summary">{nextTopicBatch.overall_strategy}</p>
              <div className="performance-topic-batch-list">
                {nextTopicBatch.items.map((item, index) => (
                  <div key={`${item.title_direction}-${index}`} className="performance-topic-item">
                    <div className="performance-topic-item-head">
                      <span className="performance-topic-index">{index + 1}</span>
                      <strong>{item.title_direction}</strong>
                    </div>
                    <div className="performance-topic-tags">
                      <span className="badge badge-purple">{item.content_type}</span>
                      {item.content_pillar ? <span className="badge badge-green">{item.content_pillar}</span> : null}
                      {item.imported_day_number ? <span className="badge badge-blue">Day {item.imported_day_number}</span> : null}
                    </div>
                    {item.hook_hint ? <p className="performance-topic-copy"><strong>开头建议：</strong>{item.hook_hint}</p> : null}
                    {item.why_this_angle ? <p className="performance-topic-copy"><strong>为什么做：</strong>{item.why_this_angle}</p> : null}
                    <div className="performance-topic-actions">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => importNextTopicBatchItemMutation.mutate({ itemIndex: index })}
                        disabled={importNextTopicBatchItemMutation.isPending || Boolean(item.imported_content_item_id)}
                      >
                        <Plus size={13} /> {item.imported_day_number ? `已加入 Day ${item.imported_day_number}` : '加入内容日历'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {performanceList.length === 0 ? (
          <div className="detail-calendar-empty">
            暂无回流数据，建议先补作品链接、关联策划条目，再录入播放、完播、互动和转化，复盘结论会更快稳定下来。
          </div>
        ) : (
          <div className="performance-table-wrap">
            <table className="performance-table">
              <thead>
                <tr>
                  <th>关联条目</th>
                  <th>标题</th>
                  <th>发布日期</th>
                  <th>播放</th>
                  <th>互动率</th>
                  <th>2秒跳出率</th>
                  <th>5秒完播率</th>
                  <th>完播率</th>
                  <th>点赞</th>
                  <th>转化</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {performanceList.map((row) => (
                  <tr key={row.id}>
                    <td className="performance-linked-cell">
                      {getContentItemLabel(row.content_item_id ? contentItemMap.get(row.content_item_id) : null)}
                    </td>
                    <td>{row.title}</td>
                    <td>{row.publish_date || '-'}</td>
                    <td>{formatMetricNumber(row.views)}</td>
                    <td>{formatMetricPercent(getPerformanceEngagementRate(row))}</td>
                    <td>{row.bounce_2s_rate != null ? `${Number(row.bounce_2s_rate).toFixed(1)}%` : '-'}</td>
                    <td>{row.completion_5s_rate != null ? `${Number(row.completion_5s_rate).toFixed(1)}%` : '-'}</td>
                    <td>{row.completion_rate != null ? `${Number(row.completion_rate).toFixed(1)}%` : '-'}</td>
                    <td>{formatMetricNumber(row.likes)}</td>
                    <td>{formatMetricNumber(row.conversions)}</td>
                    <td>
                      <div className="performance-actions">
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => {
                            setEditingPerformance(row);
                            setShowPerformanceModal(true);
                          }}
                        >
                          <Pencil size={12} /> 编辑
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => removePerformanceMutation.mutate(row.id)}
                          disabled={removePerformanceMutation.isPending}
                        >
                          <Trash2 size={12} /> 删除
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

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
