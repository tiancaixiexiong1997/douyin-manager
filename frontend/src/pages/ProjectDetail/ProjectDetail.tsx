import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { bloggerApi, downloadApi, planningApi, taskApi, type ContentCalendarItem, type ContentItem, type ContentPerformance, type ContentPerformanceCreateRequest, type UpdatePlanningRequest, type TaskCenterItem, type TaskCenterListResponse } from '../../api/client';
import { CustomSelect } from '../../components/CustomSelect';
import { ArrowLeft, Loader2, ChevronDown, ChevronUp, Sparkles, Calendar, Pencil, Save, X, RefreshCw } from '../../components/Icons';
import { toBackendTimestamp } from '../../utils/datetime';
import { CalendarPanel } from './CalendarPanel';
import { PerformancePanel } from './PerformancePanel';
import { ScriptModal } from './ScriptModal';
import './ProjectDetail.css';

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

function getContentItemLabel(item?: Pick<ContentItem, 'day_number' | 'title_direction'> | null): string {
  if (!item) return '未关联策划条目';
  return `第 ${item.day_number} 天 · ${item.title_direction}`;
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
  const [showEditProject, setShowEditProject] = useState(false);
  const [showEditPlan, setShowEditPlan] = useState(false);
  const [showPerformanceModal, setShowPerformanceModal] = useState(false);
  const [editingPerformance, setEditingPerformance] = useState<ContentPerformance | null>(null);

  const { data: project, isLoading } = useQuery({
    queryKey: ['project', id],
    queryFn: () => planningApi.get(id!),
  });
  const { data: bloggers = [] } = useQuery({
    queryKey: ['bloggers'],
    queryFn: () => bloggerApi.list(),
  });
  const projectContentItemIdSet = useMemo(
    () => new Set((project?.content_items || []).map((item) => item.id)),
    [project?.content_items],
  );

  const { data: scriptTaskPage } = useQuery({
    queryKey: ['content-script-tasks', id],
    queryFn: () =>
      taskApi.list({
        entity_type: 'content_item',
        task_type: 'planning_script_generate',
        limit: 200,
      }),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const page = query.state.data as TaskCenterListResponse | undefined;
      if (!page) return false;
      const hasPendingTasks = page.items.some((task) => isPendingTask(task) && projectContentItemIdSet.has(task.entity_id));
      return hasPendingTasks ? 3000 : false;
    },
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
    refetchInterval: (query) => {
      const page = query.state.data as TaskCenterListResponse | undefined;
      if (!page) return false;
      return page.items.some((task) => isPendingTask(task)) ? 3000 : false;
    },
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
  const projectScriptTasks = useMemo(
    () => (scriptTaskPage?.items || []).filter((task) => projectContentItemIdSet.has(task.entity_id)),
    [projectContentItemIdSet, scriptTaskPage],
  );
  const lastTaskRefreshSignatureRef = useRef<string | null>(null);

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
  const isStrategyRegenerating = Boolean(hasStrategy && (currentStage === 'strategy_generating' || isPendingTask(latestStrategyTask)));
  const taskDrivenRefreshSignature = useMemo(() => JSON.stringify({
    strategy: latestStrategyTask ? [latestStrategyTask.status, latestStrategyTask.progress_step, latestStrategyTask.updated_at] : null,
    calendar: latestCalendarTask ? [latestCalendarTask.status, latestCalendarTask.progress_step, latestCalendarTask.updated_at] : null,
    scripts: projectScriptTasks
      .map((task) => `${task.entity_id}:${task.status}:${task.progress_step || ''}:${task.updated_at}`)
      .sort(),
  }), [latestCalendarTask, latestStrategyTask, projectScriptTasks]);

  useEffect(() => {
    lastTaskRefreshSignatureRef.current = null;
  }, [id]);

  useEffect(() => {
    if (!id || !project) return;
    if (!taskDrivenRefreshSignature) return;
    if (lastTaskRefreshSignatureRef.current === null) {
      lastTaskRefreshSignatureRef.current = taskDrivenRefreshSignature;
      return;
    }
    if (lastTaskRefreshSignatureRef.current === taskDrivenRefreshSignature) return;
    lastTaskRefreshSignatureRef.current = taskDrivenRefreshSignature;
    qc.invalidateQueries({ queryKey: ['project', id] });
  }, [id, project, qc, taskDrivenRefreshSignature]);

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
