import { createPortal } from 'react-dom';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { planningApi, type AccountPlan } from '../../api/client';
import { Save, X } from '../../components/Icons';

function splitChineseList(value: string): string[] {
  return value
    .split(/[、,，\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function stringifyJson(value: unknown): string {
  return JSON.stringify(value ?? [], null, 2);
}

function parseJsonArray(value: string, label: string): unknown[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error(`${label} JSON 格式有误`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} 必须是 JSON 数组`);
  }
  return parsed;
}

export function EditPlanModal({ projectId, plan, onClose, onSaved }: {
  projectId: string;
  plan: NonNullable<AccountPlan>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const pos = plan.account_positioning;
  const strat = plan.content_strategy;
  const growth = plan.store_growth_plan;
  const hasStoreGrowthPlan = Boolean(growth);

  const [legacyForm, setLegacyForm] = useState({
    core_identity: pos?.core_identity || '',
    bio_suggestion: pos?.bio_suggestion || '',
    personality_tags: pos?.personality_tags?.join('、') || '',
    target_audience_detail: pos?.target_audience_detail || '',
    differentiation: pos?.differentiation || '',
    user_value: pos?.user_value || '',
    follow_reason: pos?.follow_reason || '',
    content_pillars: pos?.content_pillars ? stringifyJson(pos.content_pillars) : '[]',
    primary_format: strat?.primary_format || '',
    posting_frequency: strat?.posting_frequency || '',
    best_posting_times: strat?.best_posting_times?.join('、') || '',
    content_tone: strat?.content_tone || '',
    stop_scroll_reason: strat?.stop_scroll_reason || '',
    interaction_trigger: strat?.interaction_trigger || '',
    hook_template: strat?.hook_template || '',
    cta_template: strat?.cta_template || '',
  });

  const [storeForm, setStoreForm] = useState({
    market_position: growth?.store_positioning?.market_position || '',
    primary_scene: growth?.store_positioning?.primary_scene || '',
    target_audience_detail: growth?.store_positioning?.target_audience_detail || '',
    core_store_value: growth?.store_positioning?.core_store_value || '',
    differentiation: growth?.store_positioning?.differentiation || '',
    avoid_positioning: growth?.store_positioning?.avoid_positioning?.join('、') || '',
    stop_scroll_triggers: growth?.decision_triggers?.stop_scroll_triggers?.join('、') || '',
    visit_decision_factors: growth?.decision_triggers?.visit_decision_factors?.join('、') || '',
    common_hesitations: growth?.decision_triggers?.common_hesitations?.join('、') || '',
    trust_builders: growth?.decision_triggers?.trust_builders?.join('、') || '',
    primary_formats: stringifyJson(growth?.content_model?.primary_formats || []),
    content_pillars: stringifyJson(growth?.content_model?.content_pillars || []),
    traffic_hooks: growth?.content_model?.traffic_hooks?.join('、') || '',
    interaction_triggers: growth?.content_model?.interaction_triggers?.join('、') || '',
    recommended_roles: stringifyJson(growth?.on_camera_strategy?.recommended_roles || []),
    light_persona: growth?.on_camera_strategy?.light_persona || '',
    persona_boundaries: growth?.on_camera_strategy?.persona_boundaries?.join('、') || '',
    traffic_to_trust: growth?.conversion_path?.traffic_to_trust || '',
    trust_to_visit: growth?.conversion_path?.trust_to_visit || '',
    soft_cta_templates: growth?.conversion_path?.soft_cta_templates?.join('、') || '',
    hard_sell_boundaries: growth?.conversion_path?.hard_sell_boundaries?.join('、') || '',
    posting_frequency: growth?.execution_rules?.posting_frequency || '',
    best_posting_times: growth?.execution_rules?.best_posting_times?.join('、') || '',
    batch_shoot_scenes: growth?.execution_rules?.batch_shoot_scenes?.join('、') || '',
    must_capture_elements: growth?.execution_rules?.must_capture_elements?.join('、') || '',
    quality_checklist: growth?.execution_rules?.quality_checklist?.join('、') || '',
  });

  const [jsonErrors, setJsonErrors] = useState({
    content_pillars: '',
    primary_formats: '',
    recommended_roles: '',
  });

  const mutation = useMutation({
    mutationFn: () => {
      if (hasStoreGrowthPlan) {
        let primaryFormats: unknown[];
        let contentPillars: unknown[];
        let recommendedRoles: unknown[];
        try {
          primaryFormats = parseJsonArray(storeForm.primary_formats, '主要内容模型');
          contentPillars = parseJsonArray(storeForm.content_pillars, '内容支柱');
          recommendedRoles = parseJsonArray(storeForm.recommended_roles, '推荐出镜角色');
          setJsonErrors({ content_pillars: '', primary_formats: '', recommended_roles: '' });
        } catch (error) {
          const message = error instanceof Error ? error.message : 'JSON 格式有误';
          setJsonErrors({
            content_pillars: message.includes('内容支柱') ? message : '',
            primary_formats: message.includes('主要内容模型') ? message : '',
            recommended_roles: message.includes('推荐出镜角色') ? message : '',
          });
          throw error instanceof Error ? error : new Error(message);
        }

        const newPlan: AccountPlan = {
          ...plan,
          store_growth_plan: {
            store_positioning: {
              market_position: storeForm.market_position,
              primary_scene: storeForm.primary_scene,
              target_audience_detail: storeForm.target_audience_detail,
              core_store_value: storeForm.core_store_value,
              differentiation: storeForm.differentiation,
              avoid_positioning: splitChineseList(storeForm.avoid_positioning),
            },
            decision_triggers: {
              stop_scroll_triggers: splitChineseList(storeForm.stop_scroll_triggers),
              visit_decision_factors: splitChineseList(storeForm.visit_decision_factors),
              common_hesitations: splitChineseList(storeForm.common_hesitations),
              trust_builders: splitChineseList(storeForm.trust_builders),
            },
            content_model: {
              primary_formats: primaryFormats as Array<{ name: string; fit_reason: string; ratio: string }>,
              content_pillars: contentPillars as Array<{ name: string; description: string; scene_source: string }>,
              traffic_hooks: splitChineseList(storeForm.traffic_hooks),
              interaction_triggers: splitChineseList(storeForm.interaction_triggers),
            },
            on_camera_strategy: {
              recommended_roles: recommendedRoles as Array<{ role: string; responsibility: string; expression_style: string }>,
              light_persona: storeForm.light_persona,
              persona_boundaries: splitChineseList(storeForm.persona_boundaries),
            },
            conversion_path: {
              traffic_to_trust: storeForm.traffic_to_trust,
              trust_to_visit: storeForm.trust_to_visit,
              soft_cta_templates: splitChineseList(storeForm.soft_cta_templates),
              hard_sell_boundaries: splitChineseList(storeForm.hard_sell_boundaries),
            },
            execution_rules: {
              posting_frequency: storeForm.posting_frequency,
              best_posting_times: splitChineseList(storeForm.best_posting_times),
              batch_shoot_scenes: splitChineseList(storeForm.batch_shoot_scenes),
              must_capture_elements: splitChineseList(storeForm.must_capture_elements),
              quality_checklist: splitChineseList(storeForm.quality_checklist),
            },
          },
        };
        return planningApi.update(projectId, { account_plan: newPlan });
      }

      let contentPillars: unknown[];
      try {
        contentPillars = parseJsonArray(legacyForm.content_pillars, '内容支柱');
        setJsonErrors((current) => ({ ...current, content_pillars: '' }));
      } catch (error) {
        const message = error instanceof Error ? error.message : '内容支柱 JSON 格式有误';
        setJsonErrors((current) => ({ ...current, content_pillars: message }));
        throw error instanceof Error ? error : new Error(message);
      }

      const newPlan: AccountPlan = {
        ...plan,
        account_positioning: {
          core_identity: legacyForm.core_identity,
          bio_suggestion: legacyForm.bio_suggestion,
          personality_tags: splitChineseList(legacyForm.personality_tags),
          target_audience_detail: legacyForm.target_audience_detail,
          content_pillars: contentPillars as Array<{ name: string; description: string; ratio: string }>,
          differentiation: legacyForm.differentiation,
          user_value: legacyForm.user_value,
          follow_reason: legacyForm.follow_reason,
        },
        content_strategy: {
          primary_format: legacyForm.primary_format,
          posting_frequency: legacyForm.posting_frequency,
          best_posting_times: splitChineseList(legacyForm.best_posting_times),
          content_tone: legacyForm.content_tone,
          stop_scroll_reason: legacyForm.stop_scroll_reason,
          interaction_trigger: legacyForm.interaction_trigger,
          hook_template: legacyForm.hook_template,
          cta_template: legacyForm.cta_template,
        },
      };
      return planningApi.update(projectId, { account_plan: newPlan });
    },
    onSuccess: onSaved,
  });

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal edit-plan-modal animate-scale-in" style={{ maxWidth: 720 }} onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{hasStoreGrowthPlan ? '编辑实体店增长策划' : '编辑旧版策略字段'}</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4 edit-plan-modal-body" style={{ padding: '0 0 4px' }}>
          {hasStoreGrowthPlan ? (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>门店增长定位</div>
              <div className="form-group">
                <label className="form-label">同城市场定位</label>
                <textarea className="form-input form-textarea" rows={2} value={storeForm.market_position} onChange={(event) => setStoreForm((current) => ({ ...current, market_position: event.target.value }))} />
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">核心消费场景</label>
                  <input className="form-input" value={storeForm.primary_scene} onChange={(event) => setStoreForm((current) => ({ ...current, primary_scene: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">目标客群细化</label>
                  <input className="form-input" value={storeForm.target_audience_detail} onChange={(event) => setStoreForm((current) => ({ ...current, target_audience_detail: event.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">核心到店价值</label>
                <textarea className="form-input form-textarea" rows={2} value={storeForm.core_store_value} onChange={(event) => setStoreForm((current) => ({ ...current, core_store_value: event.target.value }))} />
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">差异化优势</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.differentiation} onChange={(event) => setStoreForm((current) => ({ ...current, differentiation: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">避免走的定位 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号或逗号分隔）</span></label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.avoid_positioning} onChange={(event) => setStoreForm((current) => ({ ...current, avoid_positioning: event.target.value }))} />
                </div>
              </div>

              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>用户决策触发</div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">刷到停留触发点</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.stop_scroll_triggers} onChange={(event) => setStoreForm((current) => ({ ...current, stop_scroll_triggers: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">决定到店的因素</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.visit_decision_factors} onChange={(event) => setStoreForm((current) => ({ ...current, visit_decision_factors: event.target.value }))} />
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">用户犹豫点</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.common_hesitations} onChange={(event) => setStoreForm((current) => ({ ...current, common_hesitations: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">建立信任的证据</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.trust_builders} onChange={(event) => setStoreForm((current) => ({ ...current, trust_builders: event.target.value }))} />
                </div>
              </div>

              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>内容打法</div>
              <div className="form-group">
                <label className="form-label">主要内容模型 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 name/fit_reason/ratio）</span></label>
                <textarea className="form-input form-textarea" rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }}
                  value={storeForm.primary_formats}
                  onChange={(event) => { setStoreForm((current) => ({ ...current, primary_formats: event.target.value })); setJsonErrors((current) => ({ ...current, primary_formats: '' })); }}
                />
                {jsonErrors.primary_formats && <div className="error-tip" style={{ marginTop: 4 }}>{jsonErrors.primary_formats}</div>}
              </div>
              <div className="form-group">
                <label className="form-label">内容支柱 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 name/description/scene_source）</span></label>
                <textarea className="form-input form-textarea" rows={6} style={{ fontFamily: 'monospace', fontSize: 12 }}
                  value={storeForm.content_pillars}
                  onChange={(event) => { setStoreForm((current) => ({ ...current, content_pillars: event.target.value })); setJsonErrors((current) => ({ ...current, content_pillars: '' })); }}
                />
                {jsonErrors.content_pillars && <div className="error-tip" style={{ marginTop: 4 }}>{jsonErrors.content_pillars}</div>}
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">流量钩子</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.traffic_hooks} onChange={(event) => setStoreForm((current) => ({ ...current, traffic_hooks: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">互动触发点</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.interaction_triggers} onChange={(event) => setStoreForm((current) => ({ ...current, interaction_triggers: event.target.value }))} />
                </div>
              </div>

              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>出镜策略</div>
              <div className="form-group">
                <label className="form-label">推荐出镜角色 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 role/responsibility/expression_style）</span></label>
                <textarea className="form-input form-textarea" rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }}
                  value={storeForm.recommended_roles}
                  onChange={(event) => { setStoreForm((current) => ({ ...current, recommended_roles: event.target.value })); setJsonErrors((current) => ({ ...current, recommended_roles: '' })); }}
                />
                {jsonErrors.recommended_roles && <div className="error-tip" style={{ marginTop: 4 }}>{jsonErrors.recommended_roles}</div>}
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">轻人设识别点</label>
                  <input className="form-input" value={storeForm.light_persona} onChange={(event) => setStoreForm((current) => ({ ...current, light_persona: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">人设边界</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.persona_boundaries} onChange={(event) => setStoreForm((current) => ({ ...current, persona_boundaries: event.target.value }))} />
                </div>
              </div>

              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>转化承接与执行</div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">流量如何过渡到信任</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.traffic_to_trust} onChange={(event) => setStoreForm((current) => ({ ...current, traffic_to_trust: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">信任如何过渡到到店</label>
                  <textarea className="form-input form-textarea" rows={3} value={storeForm.trust_to_visit} onChange={(event) => setStoreForm((current) => ({ ...current, trust_to_visit: event.target.value }))} />
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">软 CTA 模板</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.soft_cta_templates} onChange={(event) => setStoreForm((current) => ({ ...current, soft_cta_templates: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">硬卖边界</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.hard_sell_boundaries} onChange={(event) => setStoreForm((current) => ({ ...current, hard_sell_boundaries: event.target.value }))} />
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">发布频率</label>
                  <input className="form-input" value={storeForm.posting_frequency} onChange={(event) => setStoreForm((current) => ({ ...current, posting_frequency: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">推荐发布时间</label>
                  <input className="form-input" value={storeForm.best_posting_times} onChange={(event) => setStoreForm((current) => ({ ...current, best_posting_times: event.target.value }))} />
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">适合连拍的场景</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.batch_shoot_scenes} onChange={(event) => setStoreForm((current) => ({ ...current, batch_shoot_scenes: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">每次必抓元素</label>
                  <textarea className="form-input form-textarea" rows={2} value={storeForm.must_capture_elements} onChange={(event) => setStoreForm((current) => ({ ...current, must_capture_elements: event.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">执行检查清单</label>
                <textarea className="form-input form-textarea" rows={3} value={storeForm.quality_checklist} onChange={(event) => setStoreForm((current) => ({ ...current, quality_checklist: event.target.value }))} />
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>账号定位</div>
              <div className="form-group">
                <label className="form-label">核心定位 Slogan</label>
                <input className="form-input" value={legacyForm.core_identity} onChange={(event) => setLegacyForm((current) => ({ ...current, core_identity: event.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">主页简介建议</label>
                <textarea className="form-input form-textarea" rows={2} value={legacyForm.bio_suggestion} onChange={(event) => setLegacyForm((current) => ({ ...current, bio_suggestion: event.target.value }))} />
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">人设标签 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号或逗号分隔）</span></label>
                  <input className="form-input" value={legacyForm.personality_tags} onChange={(event) => setLegacyForm((current) => ({ ...current, personality_tags: event.target.value }))} placeholder="如：专业、亲切、幽默" />
                </div>
                <div className="form-group">
                  <label className="form-label">目标受众细化</label>
                  <input className="form-input" value={legacyForm.target_audience_detail} onChange={(event) => setLegacyForm((current) => ({ ...current, target_audience_detail: event.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">差异化优势</label>
                <input className="form-input" value={legacyForm.differentiation} onChange={(event) => setLegacyForm((current) => ({ ...current, differentiation: event.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">用户持续获得什么</label>
                <textarea className="form-input form-textarea" rows={3} value={legacyForm.user_value} onChange={(event) => setLegacyForm((current) => ({ ...current, user_value: event.target.value }))} placeholder="用户持续看下去，能稳定获得什么具体判断、方法或避坑价值" />
              </div>
              <div className="form-group">
                <label className="form-label">用户为什么会关注</label>
                <textarea className="form-input form-textarea" rows={3} value={legacyForm.follow_reason} onChange={(event) => setLegacyForm((current) => ({ ...current, follow_reason: event.target.value }))} placeholder="为什么不是看完就走，而是愿意继续关注你后续内容" />
              </div>
              <div className="form-group">
                <label className="form-label">内容支柱 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（JSON 数组，每项含 name/ratio/description）</span></label>
                <textarea className="form-input form-textarea" rows={5} style={{ fontFamily: 'monospace', fontSize: 12 }}
                  value={legacyForm.content_pillars}
                  onChange={(event) => { setLegacyForm((current) => ({ ...current, content_pillars: event.target.value })); setJsonErrors((current) => ({ ...current, content_pillars: '' })); }}
                />
                {jsonErrors.content_pillars && <div className="error-tip" style={{ marginTop: 4 }}>{jsonErrors.content_pillars}</div>}
              </div>

              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>内容策略</div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">内容形式</label>
                  <input className="form-input" value={legacyForm.primary_format} onChange={(event) => setLegacyForm((current) => ({ ...current, primary_format: event.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">发布频率</label>
                  <input className="form-input" value={legacyForm.posting_frequency} onChange={(event) => setLegacyForm((current) => ({ ...current, posting_frequency: event.target.value }))} />
                </div>
              </div>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">最佳发布时间 <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>（顿号分隔）</span></label>
                  <input className="form-input" value={legacyForm.best_posting_times} onChange={(event) => setLegacyForm((current) => ({ ...current, best_posting_times: event.target.value }))} placeholder="如：18:00、21:00" />
                </div>
                <div className="form-group">
                  <label className="form-label">内容基调</label>
                  <input className="form-input" value={legacyForm.content_tone} onChange={(event) => setLegacyForm((current) => ({ ...current, content_tone: event.target.value }))} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">用户为什么会停下来继续看</label>
                <textarea className="form-input form-textarea" rows={3} value={legacyForm.stop_scroll_reason} onChange={(event) => setLegacyForm((current) => ({ ...current, stop_scroll_reason: event.target.value }))} placeholder="陌生用户刷到时，具体会被什么信息回报、冲突或判断点留下来" />
              </div>
              <div className="form-group">
                <label className="form-label">互动触发点</label>
                <textarea className="form-input form-textarea" rows={3} value={legacyForm.interaction_trigger} onChange={(event) => setLegacyForm((current) => ({ ...current, interaction_trigger: event.target.value }))} placeholder="什么会让用户愿意评论、收藏、私信，而不是只看不动" />
              </div>
              <div className="form-group">
                <label className="form-label">钩子模板</label>
                <input className="form-input" value={legacyForm.hook_template} onChange={(event) => setLegacyForm((current) => ({ ...current, hook_template: event.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">CTA 模板</label>
                <input className="form-input" value={legacyForm.cta_template} onChange={(event) => setLegacyForm((current) => ({ ...current, cta_template: event.target.value }))} />
              </div>
            </>
          )}
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
