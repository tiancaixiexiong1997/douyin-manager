import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { planningApi, type AccountPlan } from '../../api/client';
import { Save, X } from '../../components/Icons';

export function EditPlanModal({ projectId, plan, onClose, onSaved }: {
  projectId: string;
  plan: NonNullable<AccountPlan>;
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
      const newPlan: AccountPlan = {
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
      <div className="modal edit-plan-modal animate-scale-in" style={{ maxWidth: 640 }} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">编辑账号定位方案</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4 edit-plan-modal-body" style={{ padding: '0 0 4px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>账号定位</div>
          <div className="form-group">
            <label className="form-label">核心定位 Slogan</label>
            <input className="form-input" value={form.core_identity} onChange={(event) => setForm((current) => ({ ...current, core_identity: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">主页简介建议</label>
            <textarea className="form-input form-textarea" rows={2} value={form.bio_suggestion} onChange={(event) => setForm((current) => ({ ...current, bio_suggestion: event.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">人设标签 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号或逗号分隔）</span></label>
              <input className="form-input" value={form.personality_tags} onChange={(event) => setForm((current) => ({ ...current, personality_tags: event.target.value }))} placeholder="如：专业、亲切、幽默" />
            </div>
            <div className="form-group">
              <label className="form-label">目标受众细化</label>
              <input className="form-input" value={form.target_audience_detail} onChange={(event) => setForm((current) => ({ ...current, target_audience_detail: event.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">差异化优势</label>
            <input className="form-input" value={form.differentiation} onChange={(event) => setForm((current) => ({ ...current, differentiation: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">用户持续获得什么</label>
            <textarea className="form-input form-textarea" rows={3} value={form.user_value} onChange={(event) => setForm((current) => ({ ...current, user_value: event.target.value }))} placeholder="用户持续看下去，能稳定获得什么具体判断、方法或避坑价值" />
          </div>
          <div className="form-group">
            <label className="form-label">用户为什么会关注</label>
            <textarea className="form-input form-textarea" rows={3} value={form.follow_reason} onChange={(event) => setForm((current) => ({ ...current, follow_reason: event.target.value }))} placeholder="为什么不是看完就走，而是愿意继续关注你后续内容" />
          </div>
          <div className="form-group">
            <label className="form-label">内容支柱 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 name/ratio/description）</span></label>
            <textarea className="form-input form-textarea" rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }}
              value={form.content_pillars}
              onChange={(event) => { setForm((current) => ({ ...current, content_pillars: event.target.value })); setPillarsError(''); }}
            />
            {pillarsError && <div className="error-tip" style={{ marginTop: 4 }}>{pillarsError}</div>}
          </div>

          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>内容策略</div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">内容形式</label>
              <input className="form-input" value={form.primary_format} onChange={(event) => setForm((current) => ({ ...current, primary_format: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">发布频率</label>
              <input className="form-input" value={form.posting_frequency} onChange={(event) => setForm((current) => ({ ...current, posting_frequency: event.target.value }))} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">最佳发布时间 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号分隔）</span></label>
              <input className="form-input" value={form.best_posting_times} onChange={(event) => setForm((current) => ({ ...current, best_posting_times: event.target.value }))} placeholder="如：18:00、21:00" />
            </div>
            <div className="form-group">
              <label className="form-label">内容基调</label>
              <input className="form-input" value={form.content_tone} onChange={(event) => setForm((current) => ({ ...current, content_tone: event.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">用户为什么会停下来继续看</label>
            <textarea className="form-input form-textarea" rows={3} value={form.stop_scroll_reason} onChange={(event) => setForm((current) => ({ ...current, stop_scroll_reason: event.target.value }))} placeholder="陌生用户刷到时，具体会被什么信息回报、冲突或判断点留下来" />
          </div>
          <div className="form-group">
            <label className="form-label">互动触发点</label>
            <textarea className="form-input form-textarea" rows={3} value={form.interaction_trigger} onChange={(event) => setForm((current) => ({ ...current, interaction_trigger: event.target.value }))} placeholder="什么会让用户愿意评论、收藏、私信，而不是只看不动" />
          </div>
          <div className="form-group">
            <label className="form-label">钩子模板</label>
            <input className="form-input" value={form.hook_template} onChange={(event) => setForm((current) => ({ ...current, hook_template: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">CTA 模板</label>
            <input className="form-input" value={form.cta_template} onChange={(event) => setForm((current) => ({ ...current, cta_template: event.target.value }))} />
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
