import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { planningApi, type UpdatePlanningRequest } from '../../api/client';
import { Save, X } from '../../components/Icons';

function splitChineseList(value: string): string[] {
  return value
    .split(/[、,，\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function EditProjectModal({ project, onClose, onSaved }: {
  project: {
    id: string;
    client_name: string;
    industry: string;
    target_audience: string;
    unique_advantage?: string;
    ip_requirements: string;
    style_preference?: string;
    business_goal?: string;
    store_profile?: {
      city?: string;
      business_district?: string;
      store_type?: string;
      avg_ticket?: string;
      core_products_or_services?: string[];
      top_reasons_to_choose?: string[];
      customer_common_questions?: string[];
      common_hesitations?: string[];
      primary_consumption_scenes?: string[];
      on_camera_roles?: string[];
      shootable_scenes?: string[];
      peak_hours?: string[];
      store_constraints?: string[];
    };
  };
  onClose: () => void;
  onSaved: () => void;
}) {
  const storeProfile = project.store_profile || {};
  const [form, setForm] = useState<UpdatePlanningRequest>({
    client_name: project.client_name,
    industry: project.industry,
    target_audience: project.target_audience,
    unique_advantage: project.unique_advantage || '',
    ip_requirements: project.ip_requirements,
    style_preference: project.style_preference || '',
    business_goal: project.business_goal || '',
    store_profile: {
      city: storeProfile.city || '',
      business_district: storeProfile.business_district || '',
      store_type: storeProfile.store_type || '',
      avg_ticket: storeProfile.avg_ticket || '',
      core_products_or_services: storeProfile.core_products_or_services || [],
      top_reasons_to_choose: storeProfile.top_reasons_to_choose || [],
      customer_common_questions: storeProfile.customer_common_questions || [],
      common_hesitations: storeProfile.common_hesitations || [],
      primary_consumption_scenes: storeProfile.primary_consumption_scenes || [],
      on_camera_roles: storeProfile.on_camera_roles || [],
      shootable_scenes: storeProfile.shootable_scenes || [],
      peak_hours: storeProfile.peak_hours || [],
      store_constraints: storeProfile.store_constraints || [],
    },
  });
  const [storeProfileText, setStoreProfileText] = useState({
    core_products_or_services: (storeProfile.core_products_or_services || []).join('、'),
    top_reasons_to_choose: (storeProfile.top_reasons_to_choose || []).join('、'),
    customer_common_questions: (storeProfile.customer_common_questions || []).join('、'),
    common_hesitations: (storeProfile.common_hesitations || []).join('、'),
    primary_consumption_scenes: (storeProfile.primary_consumption_scenes || []).join('、'),
    on_camera_roles: (storeProfile.on_camera_roles || []).join('、'),
    shootable_scenes: (storeProfile.shootable_scenes || []).join('、'),
    peak_hours: (storeProfile.peak_hours || []).join('、'),
    store_constraints: (storeProfile.store_constraints || []).join('、'),
  });

  const mutation = useMutation({
    mutationFn: (data: UpdatePlanningRequest) =>
      planningApi.update(project.id, {
        ...data,
        store_profile: {
          ...data.store_profile,
          core_products_or_services: splitChineseList(storeProfileText.core_products_or_services),
          top_reasons_to_choose: splitChineseList(storeProfileText.top_reasons_to_choose),
          customer_common_questions: splitChineseList(storeProfileText.customer_common_questions),
          common_hesitations: splitChineseList(storeProfileText.common_hesitations),
          primary_consumption_scenes: splitChineseList(storeProfileText.primary_consumption_scenes),
          on_camera_roles: splitChineseList(storeProfileText.on_camera_roles),
          shootable_scenes: splitChineseList(storeProfileText.shootable_scenes),
          peak_hours: splitChineseList(storeProfileText.peak_hours),
          store_constraints: splitChineseList(storeProfileText.store_constraints),
        },
      }),
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
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">所在城市</label>
              <input className="form-input" value={form.store_profile?.city || ''} onChange={(event) => setForm((current) => ({ ...current, store_profile: { ...current.store_profile, city: event.target.value } }))} />
            </div>
            <div className="form-group">
              <label className="form-label">商圈 / 区域</label>
              <input className="form-input" value={form.store_profile?.business_district || ''} onChange={(event) => setForm((current) => ({ ...current, store_profile: { ...current.store_profile, business_district: event.target.value } }))} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">门店类型</label>
              <input className="form-input" value={form.store_profile?.store_type || ''} onChange={(event) => setForm((current) => ({ ...current, store_profile: { ...current.store_profile, store_type: event.target.value } }))} />
            </div>
            <div className="form-group">
              <label className="form-label">客单价</label>
              <input className="form-input" value={form.store_profile?.avg_ticket || ''} onChange={(event) => setForm((current) => ({ ...current, store_profile: { ...current.store_profile, avg_ticket: event.target.value } }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">目标受众画像 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.target_audience || ''} onChange={(event) => setForm((current) => ({ ...current, target_audience: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">主营产品 / 服务</label>
            <textarea className="form-input form-textarea" rows={2} value={storeProfileText.core_products_or_services} onChange={(event) => setStoreProfileText((current) => ({ ...current, core_products_or_services: event.target.value }))} />
          </div>
          <div className="form-group">
            <label className="form-label">独特优势/亮点</label>
            <input className="form-input" value={form.unique_advantage || ''} onChange={(event) => setForm((current) => ({ ...current, unique_advantage: event.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">顾客为什么选你</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.top_reasons_to_choose} onChange={(event) => setStoreProfileText((current) => ({ ...current, top_reasons_to_choose: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">顾客最常犹豫什么</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.common_hesitations} onChange={(event) => setStoreProfileText((current) => ({ ...current, common_hesitations: event.target.value }))} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">顾客最常问的问题</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.customer_common_questions} onChange={(event) => setStoreProfileText((current) => ({ ...current, customer_common_questions: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">主要消费场景</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.primary_consumption_scenes} onChange={(event) => setStoreProfileText((current) => ({ ...current, primary_consumption_scenes: event.target.value }))} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">IP 定位需求 *</label>
            <textarea className="form-input form-textarea" rows={2} value={form.ip_requirements || ''} onChange={(event) => setForm((current) => ({ ...current, ip_requirements: event.target.value }))} />
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">谁能出镜</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.on_camera_roles} onChange={(event) => setStoreProfileText((current) => ({ ...current, on_camera_roles: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">可拍场景</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.shootable_scenes} onChange={(event) => setStoreProfileText((current) => ({ ...current, shootable_scenes: event.target.value }))} />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">高峰时段</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.peak_hours} onChange={(event) => setStoreProfileText((current) => ({ ...current, peak_hours: event.target.value }))} />
            </div>
            <div className="form-group">
              <label className="form-label">拍摄限制</label>
              <textarea className="form-input form-textarea" rows={2} value={storeProfileText.store_constraints} onChange={(event) => setStoreProfileText((current) => ({ ...current, store_constraints: event.target.value }))} />
            </div>
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
