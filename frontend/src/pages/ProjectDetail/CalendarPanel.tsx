import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { planningApi, type ContentCalendarItem, type ContentItem, type TaskCenterItem } from '../../api/client';
import { Calendar, Loader2, Pencil, RefreshCw, Save } from '../../components/Icons';
import { notifyInfo } from '../../utils/notify';

type CalendarDisplayItem = ContentItem & { calendarMeta?: ContentCalendarItem | null };
type ProjectStage = 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed';

const SCHEDULE_GROUP_FILTER_PREFIX = 'schedule_group:';

function getCalendarScheduleMeta(item: CalendarDisplayItem): {
  shootFormat: string;
  talentRequirement: string;
  shootScene: string;
  prepRequirement: string;
  scheduleGroup: string;
} {
  return {
    shootFormat: item.calendarMeta?.shoot_format?.trim() || '待定',
    talentRequirement: item.calendarMeta?.talent_requirement?.trim() || '待安排',
    shootScene: item.calendarMeta?.shoot_scene?.trim() || '待安排',
    prepRequirement: item.calendarMeta?.prep_requirement?.trim() || '待安排',
    scheduleGroup: item.calendarMeta?.schedule_group?.trim() || item.calendarMeta?.batch_shoot_group?.trim() || '待分组',
  };
}

type CalendarPanelProps = {
  projectId: string;
  hasStrategy: boolean;
  hasCalendar: boolean;
  currentStage: ProjectStage;
  calendarDisplayItems: CalendarDisplayItem[];
  pendingRegenerationDaySet: Set<number>;
  scriptTaskMap: Map<string, TaskCenterItem>;
  onOpenItem: (item: CalendarDisplayItem) => void;
  onRegenerate: (dayNumbers: number[]) => Promise<unknown>;
  isRegeneratePending: boolean;
  regenerateError: Error | null;
};

export function CalendarPanel({
  projectId,
  hasStrategy,
  hasCalendar,
  currentStage,
  calendarDisplayItems,
  pendingRegenerationDaySet,
  scriptTaskMap,
  onOpenItem,
  onRegenerate,
  isRegeneratePending,
  regenerateError,
}: CalendarPanelProps) {
  const qc = useQueryClient();
  const [calendarFilter, setCalendarFilter] = useState<string>('all');
  const [isSelectingRegenerateDays, setIsSelectingRegenerateDays] = useState(false);
  const [regenerateSelectedDays, setRegenerateSelectedDays] = useState<number[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title_direction: '', content_type: '' });

  const updateItemMutation = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: { title_direction: string; content_type: string } }) =>
      planningApi.updateContentItem(itemId, data),
    onSuccess: () => {
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const scheduleGroupEntries = Array.from(
    calendarDisplayItems.reduce((map, item) => {
      const group = getCalendarScheduleMeta(item).scheduleGroup;
      if (!group) return map;
      map.set(group, (map.get(group) || 0) + 1);
      return map;
    }, new Map<string, number>()),
  );
  const filteredCalendarItems = calendarDisplayItems.filter((item) => {
    if (calendarFilter === 'all') return true;
    if (calendarFilter.startsWith(SCHEDULE_GROUP_FILTER_PREFIX)) {
      return getCalendarScheduleMeta(item).scheduleGroup === calendarFilter.slice(SCHEDULE_GROUP_FILTER_PREFIX.length);
    }
    return true;
  });
  const allCalendarDays = calendarDisplayItems.map((item) => item.day_number);
  const preservedDayCount = Math.max(0, calendarDisplayItems.length - regenerateSelectedDays.length);
  const displayCalendarItems = isSelectingRegenerateDays ? calendarDisplayItems : filteredCalendarItems;

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

  const submitSelectedRegeneration = async () => {
    if (calendarDisplayItems.length > 0 && regenerateSelectedDays.length === 0) {
      notifyInfo('至少勾选 1 条需要重生成的内容');
      return;
    }
    setCalendarFilter('all');
    try {
      await onRegenerate(regenerateSelectedDays);
      setIsSelectingRegenerateDays(false);
      setRegenerateSelectedDays([]);
    } catch {
      // 错误提示由 mutation state 统一展示
    }
  };

  const regenerateFullCalendar = async () => {
    setCalendarFilter('all');
    try {
      await onRegenerate([]);
    } catch {
      // 错误提示由 mutation state 统一展示
    }
  };

  if (!(hasStrategy && (hasCalendar || currentStage === 'calendar_generating'))) {
    return null;
  }

  return (
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
              onClick={() => void regenerateFullCalendar()}
              disabled={isRegeneratePending || isSelectingRegenerateDays}
            >
              <RefreshCw size={13} /> {isRegeneratePending && !isSelectingRegenerateDays ? '生成中...' : '重新生成日历'}
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={startInlineRegenerateSelection}
              disabled={isRegeneratePending || isSelectingRegenerateDays}
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
                  disabled={isRegeneratePending}
                >
                  全选
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setRegenerateSelectedDays([])}
                  disabled={isRegeneratePending}
                >
                  清空
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={cancelInlineRegenerateSelection}
                  disabled={isRegeneratePending}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => void submitSelectedRegeneration()}
                  disabled={isRegeneratePending}
                >
                  {isRegeneratePending ? (
                    <><Loader2 size={14} className="spin-icon" /> 生成中...</>
                  ) : (
                    <><RefreshCw size={14} /> 确认重生成</>
                  )}
                </button>
              </div>
            </div>
          )}
          {regenerateError && (
            <div className="error-tip">{regenerateError.message}</div>
          )}
          {displayCalendarItems.length > 0 ? (
            <div className="calendar-grid">
              {displayCalendarItems.map((item) => {
                const scheduleMeta = getCalendarScheduleMeta(item);
                const isSelectedForRegenerate = regenerateSelectedDays.includes(item.day_number);
                const isPendingRegenerate = pendingRegenerationDaySet.has(item.day_number);
                const scriptTask = scriptTaskMap.get(item.id);
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
                      onOpenItem(item);
                    }}
                  >
                    <div className="calendar-item-body">
                      {editingId === item.id ? (
                        <div className="calendar-edit-form" onClick={(event) => event.stopPropagation()}>
                          <input
                            className="form-input calendar-edit-input"
                            value={editForm.title_direction}
                            onChange={(event) => setEditForm((form) => ({ ...form, title_direction: event.target.value }))}
                            placeholder="内容方向"
                          />
                          <input
                            className="form-input calendar-edit-input"
                            value={editForm.content_type}
                            onChange={(event) => setEditForm((form) => ({ ...form, content_type: event.target.value }))}
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
                                onClick={(event) => {
                                  event.stopPropagation();
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
                            ) : (scriptTask?.status === 'queued' || scriptTask?.status === 'running') ? (
                              <span className="script-gen-label">生成中</span>
                            ) : scriptTask?.status === 'failed' ? (
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
                );
              })}
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
  );
}
