import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { planningApi, type UpdatePlanningRequest } from '../../api/client';
import { Save, X } from '../../components/Icons';

export function EditProjectModal({ project, onClose, onSaved }: {
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
      <div className="modal edit-project-modal animate-scale-in" style={{ maxWidth: 560 }} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">编辑策划信息</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4 edit-project-modal-body" style={{ padding: '0 0 4px' }}>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">客户/品牌名称 *</label>
              <input className="form-input" value={form.client_name || ''} onChange={(event) => setForm((current) => ({ ...current, client_name: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">行业垂类 *</label>
              <input className="form-input" value={form.industry || ''} onChange={(event) => setForm((current) => ({ ...current, industry: event.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">目标受众画像 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.target_audience || ''} onChange={(event) => setForm((current) => ({ ...current, target_audience: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">独特优势/亮点</label>
            <input className="form-input" value={form.unique_advantage || ''} onChange={(event) => setForm((current) => ({ ...current, unique_advantage: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">IP 定位需求 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.ip_requirements || ''} onChange={(event) => setForm((current) => ({ ...current, ip_requirements: event.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">风格偏好</label>
              <input className="form-input" value={form.style_preference || ''} onChange={(event) => setForm((current) => ({ ...current, style_preference: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">商业目标</label>
              <input className="form-input" value={form.business_goal || ''} onChange={(event) => setForm((current) => ({ ...current, business_goal: event.target.value }))} />
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
