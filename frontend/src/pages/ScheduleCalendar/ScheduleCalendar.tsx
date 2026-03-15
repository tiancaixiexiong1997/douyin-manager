import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Calendar, ChevronLeft, ChevronRight, Plus, Save, Trash2, X } from '../../components/Icons';
import { scheduleApi, type ScheduleEntry } from '../../api/client';
import { notifyError, notifySuccess } from '../../utils/notify';
import './ScheduleCalendar.css';

type ScheduleForm = {
  title: string;
  contentType: string;
  notes: string;
};

const emptyForm: ScheduleForm = {
  title: '',
  contentType: '',
  notes: '',
};

const toDateKey = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const fromDateKey = (dateKey: string) => {
  const [y, m, d] = dateKey.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
};

const addDays = (date: Date, days: number) => {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
};

const isSameMonth = (date: Date, monthAnchor: Date) =>
  date.getFullYear() === monthAnchor.getFullYear() && date.getMonth() === monthAnchor.getMonth();

const getWeekStartMonday = (date: Date) => {
  const copy = new Date(date);
  const day = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - day);
  copy.setHours(0, 0, 0, 0);
  return copy;
};

const getWeekEndSunday = (date: Date) => {
  const start = getWeekStartMonday(date);
  return addDays(start, 6);
};

const getCalendarCells = (monthAnchor: Date) => {
  const monthStart = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1);
  const monthEnd = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth() + 1, 0);
  const gridStart = getWeekStartMonday(monthStart);
  const gridEnd = getWeekEndSunday(monthEnd);
  const cells: Date[] = [];

  for (let cursor = new Date(gridStart); cursor <= gridEnd; cursor = addDays(cursor, 1)) {
    cells.push(new Date(cursor));
  }
  return cells;
};

const formatMonthLabel = (date: Date) =>
  `${date.getFullYear()} 年 ${String(date.getMonth() + 1).padStart(2, '0')} 月`;

const formatDateLabel = (dateKey: string | null) => {
  if (!dateKey) return '未选择日期';
  const date = fromDateKey(dateKey);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });
};

export default function ScheduleCalendar() {
  const queryClient = useQueryClient();
  const todayDateKey = toDateKey(new Date());
  const [monthAnchor, setMonthAnchor] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [selectedDateKey, setSelectedDateKey] = useState<string | null>(null);
  const [isFutureDetailOpen, setIsFutureDetailOpen] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalDateKey, setModalDateKey] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ScheduleForm>(emptyForm);

  const calendarCells = useMemo(() => getCalendarCells(monthAnchor), [monthAnchor]);

  const queryRange = useMemo(() => {
    const monthStart = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1);
    const monthEnd = new Date(monthAnchor.getFullYear(), monthAnchor.getMonth() + 1, 0);
    return {
      start: toDateKey(getWeekStartMonday(monthStart)),
      end: toDateKey(getWeekEndSunday(monthEnd)),
    };
  }, [monthAnchor]);
  const future30Range = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return {
      start: toDateKey(today),
      end: toDateKey(addDays(today, 29)),
    };
  }, []);

  const { data: entries = [], isLoading, isFetching } = useQuery({
    queryKey: ['schedule-entries', queryRange.start, queryRange.end],
    queryFn: () =>
      scheduleApi.list({
        start_date: queryRange.start,
        end_date: queryRange.end,
        limit: 2000,
      }),
  });
  const { data: future30Entries = [], isLoading: isFuture30Loading, isError: isFuture30Error } = useQuery({
    queryKey: ['schedule-entries', 'future-30-days', future30Range.start, future30Range.end],
    queryFn: () =>
      scheduleApi.list({
        start_date: future30Range.start,
        end_date: future30Range.end,
        limit: 2000,
      }),
  });

  const createMutation = useMutation({
    mutationFn: scheduleApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule-entries'] });
      notifySuccess('排期已添加');
    },
    onError: (err: unknown) => notifyError((err as Error)?.message || '添加排期失败'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof scheduleApi.update>[1] }) =>
      scheduleApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule-entries'] });
      notifySuccess('排期已更新');
    },
    onError: (err: unknown) => notifyError((err as Error)?.message || '更新排期失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => scheduleApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['schedule-entries'] });
      notifySuccess('排期已删除');
    },
    onError: (err: unknown) => notifyError((err as Error)?.message || '删除排期失败'),
  });

  const monthEntries = useMemo(
    () => entries.filter((entry) => isSameMonth(fromDateKey(entry.schedule_date), monthAnchor)),
    [entries, monthAnchor]
  );

  const dayMap = useMemo(() => {
    const map = new Map<string, ScheduleEntry[]>();
    for (const entry of entries) {
      const list = map.get(entry.schedule_date) || [];
      list.push(entry);
      map.set(entry.schedule_date, list);
    }
    for (const [key, list] of map) {
      list.sort((a, b) => Number(a.done) - Number(b.done) || a.created_at.localeCompare(b.created_at));
      map.set(key, list);
    }
    return map;
  }, [entries]);

  const resolvedSelectedDateKey = useMemo(() => {
    if (selectedDateKey && selectedDateKey >= todayDateKey) return selectedDateKey;
    const today = new Date();
    if (isSameMonth(today, monthAnchor)) return todayDateKey;
    const monthStartKey = toDateKey(new Date(monthAnchor.getFullYear(), monthAnchor.getMonth(), 1));
    return monthStartKey >= todayDateKey ? monthStartKey : null;
  }, [monthAnchor, selectedDateKey, todayDateKey]);

  const selectedDayEntries = useMemo(
    () => (resolvedSelectedDateKey ? dayMap.get(resolvedSelectedDateKey) || [] : []),
    [dayMap, resolvedSelectedDateKey]
  );

  const future30DoneCount = future30Entries.filter((entry) => entry.done).length;
  const future30GroupedEntries = useMemo(() => {
    const map = new Map<string, ScheduleEntry[]>();
    for (const entry of future30Entries) {
      const list = map.get(entry.schedule_date) || [];
      list.push(entry);
      map.set(entry.schedule_date, list);
    }
    const sortedDateKeys = Array.from(map.keys()).sort((a, b) => a.localeCompare(b));
    return sortedDateKeys.map((dateKey) => ({
      dateKey,
      entries: (map.get(dateKey) || []).sort((a, b) => Number(a.done) - Number(b.done) || a.created_at.localeCompare(b.created_at)),
    }));
  }, [future30Entries]);

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
  };

  const openDateModal = (dateKey: string) => {
    if (dateKey < todayDateKey) return;
    setSelectedDateKey(dateKey);
    setModalDateKey(dateKey);
    resetForm();
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setModalDateKey(null);
    resetForm();
  };

  const startEdit = (entry: ScheduleEntry) => {
    setEditingId(entry.id);
    setForm({
      title: entry.title,
      contentType: entry.content_type || '',
      notes: entry.notes || '',
    });
  };

  const handleSave = async () => {
    if (!modalDateKey) return;
    if (modalDateKey < todayDateKey) {
      notifyError('过去日期不允许新增排期');
      return;
    }
    const title = form.title.trim();
    if (!title) return;
    const contentType = form.contentType.trim();
    const notes = form.notes.trim();

    if (editingId) {
      await updateMutation.mutateAsync({
        id: editingId,
        data: {
          title,
          content_type: contentType || null,
          notes: notes || null,
        },
      });
    } else {
      await createMutation.mutateAsync({
        schedule_date: modalDateKey,
        title,
        content_type: contentType || null,
        notes: notes || null,
        done: false,
      });
    }
    resetForm();
  };

  const removeEntry = async (id: string) => {
    await deleteMutation.mutateAsync(id);
    if (editingId === id) resetForm();
  };

  return (
    <div className="schedule-page">
      <section className="schedule-hero">
        <div>
          <div className="schedule-hero-pill">
            <Calendar size={14} />
            日历排期
          </div>
          <h1>日历排期表</h1>
          <p>系统会自动识别当前日期，过去日期不可选中且不可新增排期。单击查看详情，双击打开排期设置。</p>
        </div>
        <div className="schedule-hero-stats">
          <div className="schedule-stat-card">
            <div className="schedule-stat-label">当月排期条数</div>
            <div className="schedule-stat-value">{monthEntries.length}</div>
          </div>
          <div className="schedule-stat-card">
            <div className="schedule-stat-label">未来30天总排期</div>
            <div className="schedule-stat-value">{isFuture30Loading ? '--' : isFuture30Error ? '!' : future30Entries.length}</div>
            <button
              type="button"
              className="schedule-stat-link"
              onClick={() => setIsFutureDetailOpen(true)}
              disabled={isFuture30Loading || isFuture30Error}
            >
              查看详情
            </button>
          </div>
        </div>
      </section>

      <section className="schedule-toolbar">
        <div className="schedule-month-switch">
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setMonthAnchor((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
              setSelectedDateKey(null);
            }}
          >
            <ChevronLeft size={14} />
          </button>
          <div className="schedule-month-label">{formatMonthLabel(monthAnchor)}</div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => {
              setMonthAnchor((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
              setSelectedDateKey(null);
            }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => {
            if (resolvedSelectedDateKey) openDateModal(resolvedSelectedDateKey);
          }}
          disabled={!resolvedSelectedDateKey}
        >
          <Plus size={14} /> 为所选日期新增排期
        </button>
      </section>

      <section className="schedule-main">
        <div className="schedule-calendar card">
          <div className="schedule-weekdays">
            {['一', '二', '三', '四', '五', '六', '日'].map((label) => (
              <div key={label} className="schedule-weekday">
                周{label}
              </div>
            ))}
          </div>

          {isLoading ? (
            <div className="schedule-day-empty">正在加载排期数据...</div>
          ) : (
            <div className="schedule-grid">
              {calendarCells.map((date) => {
                const dateKey = toDateKey(date);
                const dayEntries = dayMap.get(dateKey) || [];
                const inCurrentMonth = isSameMonth(date, monthAnchor);
                const isPastDate = dateKey < todayDateKey;
                const active = !isPastDate && resolvedSelectedDateKey === dateKey;
                return (
                  <button
                    type="button"
                    key={dateKey}
                    className={`schedule-cell ${inCurrentMonth ? '' : 'is-muted'} ${active ? 'is-active' : ''} ${isPastDate ? 'is-disabled' : ''}`}
                    onClick={() => {
                      if (!isPastDate) setSelectedDateKey(dateKey);
                    }}
                    onDoubleClick={() => openDateModal(dateKey)}
                    disabled={isPastDate}
                    title={isPastDate ? '过去日期不可新增排期' : undefined}
                  >
                    <div className="schedule-cell-date">{date.getDate()}</div>
                    <div className="schedule-cell-items">
                      {dayEntries.slice(0, 3).map((entry) => (
                        <div key={entry.id} className={`schedule-chip ${entry.done ? 'is-done' : ''}`} title={entry.title}>
                          {entry.title}
                        </div>
                      ))}
                      {dayEntries.length > 3 && (
                        <div className="schedule-chip schedule-chip-more">+{dayEntries.length - 3}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="schedule-day-panel card">
          <div className="schedule-day-head">
            <h3>{formatDateLabel(resolvedSelectedDateKey)}</h3>
            <span className="badge badge-purple">{selectedDayEntries.length} 条</span>
          </div>

          {!resolvedSelectedDateKey ? (
            <div className="schedule-day-empty">该月份日期已全部过期，无法选择与新增排期。</div>
          ) : selectedDayEntries.length === 0 ? (
            <div className="schedule-day-empty">当天暂无排期，双击日历日期即可创建。</div>
          ) : (
            <div className="schedule-day-list">
              {selectedDayEntries.map((entry) => (
                <div key={entry.id} className="schedule-day-item">
                  <div className="schedule-day-item-top">
                    <div className="schedule-day-project">{entry.title}</div>
                    <span className={`badge ${entry.done ? 'badge-green' : 'badge-yellow'}`}>
                      {entry.done ? '已完成' : '待完成'}
                    </span>
                  </div>
                  <div className="schedule-day-title">{entry.content_type || '未填写类型'}</div>
                  {entry.notes && <div className="schedule-day-note">{entry.notes}</div>}
                </div>
              ))}
            </div>
          )}
          {isFetching && <div className="schedule-day-fetching">数据更新中...</div>}
        </div>
      </section>

      {isModalOpen && modalDateKey && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal schedule-modal schedule-setting-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{formatDateLabel(modalDateKey)} · 排期设置</h2>
              <button className="btn btn-icon btn-ghost" onClick={closeModal}>
                <X size={16} />
              </button>
            </div>

            <div className="schedule-modal-body">
              <div className="schedule-modal-list">
                {((dayMap.get(modalDateKey) || []).length === 0) ? (
                  <div className="schedule-modal-empty">当天还没有排期，先在右侧填写一条吧。</div>
                ) : (
                  (dayMap.get(modalDateKey) || []).map((entry) => (
                    <div key={entry.id} className="schedule-modal-item">
                      <div className="schedule-modal-item-main">
                        <div className="schedule-modal-item-title">{entry.title}</div>
                        <div className="schedule-modal-item-sub">{entry.content_type || '未填写类型'}</div>
                      </div>
                      <div className="schedule-modal-item-actions">
                        <button className="btn btn-ghost btn-sm" onClick={() => startEdit(entry)}>
                          编辑
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => void removeEntry(entry.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 size={12} /> 删除
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="schedule-form">
                <div className="schedule-form-title">{editingId ? '编辑排期' : '新增排期'}</div>
                <div className="form-group">
                  <label className="form-label">排期标题 *</label>
                  <input
                    className="form-input"
                    placeholder="例如：口播选题-春季新品种草"
                    value={form.title}
                    onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">内容类型</label>
                  <input
                    className="form-input"
                    placeholder="例如：口播 / Vlog / 评测"
                    value={form.contentType}
                    onChange={(e) => setForm((prev) => ({ ...prev, contentType: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">备注</label>
                  <textarea
                    className="form-input form-textarea"
                    rows={3}
                    placeholder="填写拍摄提示、发布时间、协作人等"
                    value={form.notes}
                    onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                  />
                </div>
                <div className="schedule-form-actions">
                  {editingId && (
                    <button className="btn btn-ghost btn-sm" onClick={resetForm}>
                      取消编辑
                    </button>
                  )}
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => void handleSave()}
                    disabled={!form.title.trim() || createMutation.isPending || updateMutation.isPending}
                  >
                    <Save size={13} /> {editingId ? '保存修改' : '添加排期'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {isFutureDetailOpen && (
        <div className="modal-overlay" onClick={() => setIsFutureDetailOpen(false)}>
          <div className="modal schedule-modal schedule-future-modal animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">未来30天总排期详情</h2>
              <button className="btn btn-icon btn-ghost" onClick={() => setIsFutureDetailOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="schedule-future-summary">
              周期：{future30Range.start} 至 {future30Range.end} · 共 {future30Entries.length} 条 · 已完成 {future30DoneCount} 条
            </div>

            {future30GroupedEntries.length === 0 ? (
              <div className="schedule-day-empty">未来30天暂无排期。</div>
            ) : (
              <div className="schedule-future-list">
                {future30GroupedEntries.map((group) => (
                  <div key={group.dateKey} className="schedule-future-group">
                    <div className="schedule-future-group-head">
                      <h4>{formatDateLabel(group.dateKey)}</h4>
                      <span className="badge badge-purple">{group.entries.length} 条</span>
                    </div>
                    <div className="schedule-future-items">
                      {group.entries.map((entry) => (
                        <div key={entry.id} className="schedule-day-item">
                          <div className="schedule-day-item-top">
                            <div className="schedule-day-project">{entry.title}</div>
                            <span className={`badge ${entry.done ? 'badge-green' : 'badge-yellow'}`}>
                              {entry.done ? '已完成' : '待完成'}
                            </span>
                          </div>
                          <div className="schedule-day-title">{entry.content_type || '未填写类型'}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
