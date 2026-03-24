import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { downloadApi, planningApi, type ContentItem, type ContentPerformance, type ContentPerformanceCreateRequest } from '../../api/client';
import { CustomSelect } from '../../components/CustomSelect';
import { Save, X } from '../../components/Icons';

function getContentItemLabel(item?: Pick<ContentItem, 'day_number' | 'title_direction'> | null): string {
  if (!item) return '未关联策划条目';
  return `第 ${item.day_number} 天 · ${item.title_direction}`;
}

export function PerformanceModal({
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
    [contentItems],
  );
  const selectedContentItem = form.content_item_id ? contentItemMap.get(form.content_item_id) || null : null;

  const parseMutation = useMutation({
    mutationFn: async () => {
      const url = (form.video_url || '').trim();
      if (!url) throw new Error('请先填写作品链接');
      return downloadApi.parse(url);
    },
    onSuccess: (parsed) => {
      const publishDate = parsed.published_at ? parsed.published_at.split('T')[0] : null;
      setForm((current) => ({
        ...current,
        title: (parsed.title || current.title || '').trim(),
        platform: (parsed.platform || current.platform || 'douyin').trim(),
        publish_date: publishDate || current.publish_date || null,
        views: typeof parsed.view_count === 'number' ? parsed.view_count : (current.views ?? 0),
        likes: typeof parsed.like_count === 'number' ? parsed.like_count : (current.likes ?? 0),
        comments: typeof parsed.comment_count === 'number' ? parsed.comment_count : (current.comments ?? 0),
        shares: typeof parsed.share_count === 'number' ? parsed.share_count : (current.shares ?? 0),
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
    setForm((current) => ({ ...current, [key]: value === '' ? null : (Number.isFinite(num) ? num : null) }));
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal animate-scale-in" style={{ maxWidth: 640 }} onClick={(event) => event.stopPropagation()}>
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
                onChange={(event) => setForm((current) => ({ ...current, video_url: event.target.value }))}
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
                setForm((current) => {
                  const nextItem = nextId ? contentItemMap.get(nextId) || null : null;
                  const nextTitle = !current.title.trim() && nextItem ? nextItem.title_direction : current.title;
                  return {
                    ...current,
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
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
              />
            </div>
            <div className="form-group">
              <label className="form-label">发布日期</label>
              <input
                type="date"
                className="form-input"
                value={form.publish_date || ''}
                onChange={(event) => setForm((current) => ({ ...current, publish_date: event.target.value || null }))}
              />
            </div>
          </div>

          <div className="grid-4">
            <div className="form-group">
              <label className="form-label">播放</label>
              <input type="number" min={0} className="form-input" value={form.views ?? 0} onChange={(event) => setForm((current) => ({ ...current, views: Math.max(0, Number(event.target.value || 0)) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">点赞</label>
              <input type="number" min={0} className="form-input" value={form.likes ?? 0} onChange={(event) => setForm((current) => ({ ...current, likes: Math.max(0, Number(event.target.value || 0)) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">评论</label>
              <input type="number" min={0} className="form-input" value={form.comments ?? 0} onChange={(event) => setForm((current) => ({ ...current, comments: Math.max(0, Number(event.target.value || 0)) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">转发</label>
              <input type="number" min={0} className="form-input" value={form.shares ?? 0} onChange={(event) => setForm((current) => ({ ...current, shares: Math.max(0, Number(event.target.value || 0)) }))} />
            </div>
          </div>

          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">转化数</label>
              <input type="number" min={0} className="form-input" value={form.conversions ?? 0} onChange={(event) => setForm((current) => ({ ...current, conversions: Math.max(0, Number(event.target.value || 0)) }))} />
            </div>
            <div className="form-group">
              <label className="form-label">发布平台</label>
              <input className="form-input" value={form.platform || 'douyin'} onChange={(event) => setForm((current) => ({ ...current, platform: event.target.value }))} />
            </div>
          </div>

          <div className="grid-3">
            <div className="form-group">
              <label className="form-label">2秒跳出率(%)</label>
              <input type="number" min={0} max={100} step="0.1" className="form-input" value={form.bounce_2s_rate ?? ''} onChange={(event) => updateRate('bounce_2s_rate', event.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">5秒完播率(%)</label>
              <input type="number" min={0} max={100} step="0.1" className="form-input" value={form.completion_5s_rate ?? ''} onChange={(event) => updateRate('completion_5s_rate', event.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">整体完播率(%)</label>
              <input type="number" min={0} max={100} step="0.1" className="form-input" value={form.completion_rate ?? ''} onChange={(event) => updateRate('completion_rate', event.target.value)} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">复盘备注</label>
            <textarea
              className="form-input form-textarea"
              rows={3}
              value={form.notes || ''}
              placeholder="例如：开头前三秒用强对比，评论区多问价格，门店成交来自直播间导流"
              onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
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
