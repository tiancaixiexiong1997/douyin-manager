import type { AccountPlan } from '../../api/client';
import { ChevronDown, ChevronUp, Loader2, Pencil, RefreshCw } from '../../components/Icons';
import type { ProjectStage } from './projectDetailShared';

type StoreGrowthPanelProps = {
  storeGrowthPlan: NonNullable<AccountPlan['store_growth_plan']>;
  currentStage: ProjectStage;
  isExpanded: boolean;
  isRegenerating: boolean;
  isRegeneratePending: boolean;
  onToggleExpand: () => void;
  onRegenerate: () => void;
  onEdit: () => void;
};

function renderTextList(items?: string[]) {
  const normalized = (items || []).filter(Boolean);
  if (normalized.length === 0) return null;
  return (
    <div className="growth-chip-list">
      {normalized.map((item) => (
        <span key={item} className="growth-chip">{item}</span>
      ))}
    </div>
  );
}

export function StoreGrowthPanel({
  storeGrowthPlan,
  currentStage,
  isExpanded,
  isRegenerating,
  isRegeneratePending,
  onToggleExpand,
  onRegenerate,
  onEdit,
}: StoreGrowthPanelProps) {
  const storePositioning = storeGrowthPlan.store_positioning;
  const decisionTriggers = storeGrowthPlan.decision_triggers;
  const contentModel = storeGrowthPlan.content_model;
  const onCameraStrategy = storeGrowthPlan.on_camera_strategy;
  const conversionPath = storeGrowthPlan.conversion_path;
  const executionRules = storeGrowthPlan.execution_rules;

  return (
    <div className={`card detail-section detail-positioning ${isRegenerating ? 'detail-positioning-regenerating' : ''}`}>
      <div className={`detail-section-head ${isExpanded ? 'is-open' : ''}`} onClick={onToggleExpand}>
        <h2 className="section-title detail-section-title">实体店增长策划</h2>
        <div className="flex items-center gap-2 detail-section-actions" onClick={(event) => event.stopPropagation()}>
          {currentStage !== 'strategy_generating' && currentStage !== 'calendar_generating' && (
            <button className="btn btn-ghost btn-sm" onClick={onRegenerate} disabled={isRegeneratePending}>
              <RefreshCw size={13} /> {isRegeneratePending ? '生成中...' : '重新生成定位'}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={onEdit}>
            <Pencil size={13} /> 编辑
          </button>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {isExpanded && (
        <div className="detail-positioning-body animate-fade-in">
          {storePositioning?.market_position && (
            <div className="identity-block">
              <div className="identity-label">门店增长定位</div>
              <div className="identity-value gradient-text">{storePositioning.market_position}</div>
            </div>
          )}

          {(storePositioning?.primary_scene || storePositioning?.target_audience_detail || storePositioning?.core_store_value || storePositioning?.differentiation) && (
            <div className="strategy-grid">
              {storePositioning?.primary_scene && (
                <div className="strategy-item">
                  <div className="identity-label">核心消费场景</div>
                  <div className="strategy-value">{storePositioning.primary_scene}</div>
                </div>
              )}
              {storePositioning?.target_audience_detail && (
                <div className="strategy-item">
                  <div className="identity-label">高潜客群</div>
                  <div className="strategy-value">{storePositioning.target_audience_detail}</div>
                </div>
              )}
              {storePositioning?.core_store_value && (
                <div className="strategy-item">
                  <div className="identity-label">到店核心理由</div>
                  <div className="strategy-value">{storePositioning.core_store_value}</div>
                </div>
              )}
              {storePositioning?.differentiation && (
                <div className="strategy-item">
                  <div className="identity-label">差异化支点</div>
                  <div className="strategy-value">{storePositioning.differentiation}</div>
                </div>
              )}
            </div>
          )}

          {storePositioning?.avoid_positioning && storePositioning.avoid_positioning.length > 0 && (
            <div className="positioning-block">
              <div className="identity-label positioning-label">不建议走的方向</div>
              {renderTextList(storePositioning.avoid_positioning)}
            </div>
          )}

          {(decisionTriggers?.stop_scroll_triggers || decisionTriggers?.visit_decision_factors || decisionTriggers?.common_hesitations || decisionTriggers?.trust_builders) && (
            <div className="growth-section-block">
              <div className="identity-label positioning-label">用户决策触发点</div>
              <div className="growth-list-grid">
                {decisionTriggers?.stop_scroll_triggers && decisionTriggers.stop_scroll_triggers.length > 0 && (
                  <div className="growth-list-card">
                    <div className="growth-list-title">刷到为什么会停</div>
                    {renderTextList(decisionTriggers.stop_scroll_triggers)}
                  </div>
                )}
                {decisionTriggers?.visit_decision_factors && decisionTriggers.visit_decision_factors.length > 0 && (
                  <div className="growth-list-card">
                    <div className="growth-list-title">为什么会到店</div>
                    {renderTextList(decisionTriggers.visit_decision_factors)}
                  </div>
                )}
                {decisionTriggers?.common_hesitations && decisionTriggers.common_hesitations.length > 0 && (
                  <div className="growth-list-card">
                    <div className="growth-list-title">最常见顾虑</div>
                    {renderTextList(decisionTriggers.common_hesitations)}
                  </div>
                )}
                {decisionTriggers?.trust_builders && decisionTriggers.trust_builders.length > 0 && (
                  <div className="growth-list-card">
                    <div className="growth-list-title">最强信任证据</div>
                    {renderTextList(decisionTriggers.trust_builders)}
                  </div>
                )}
              </div>
            </div>
          )}

          {(contentModel?.primary_formats || contentModel?.content_pillars || contentModel?.traffic_hooks || contentModel?.interaction_triggers) && (
            <div className="growth-section-block">
              <div className="identity-label positioning-label">内容打法</div>
              {contentModel?.primary_formats && contentModel.primary_formats.length > 0 && (
                <div className="growth-format-grid">
                  {contentModel.primary_formats.map((item) => (
                    <div key={`${item.name}-${item.ratio}`} className="pillar-card">
                      <div className="pillar-name">{item.name}</div>
                      <div className="pillar-ratio">{item.ratio}</div>
                      <div className="pillar-desc">{item.fit_reason}</div>
                    </div>
                  ))}
                </div>
              )}
              {contentModel?.content_pillars && contentModel.content_pillars.length > 0 && (
                <div className="pillars-grid growth-pillar-grid">
                  {contentModel.content_pillars.map((pillar) => (
                    <div key={pillar.name} className="pillar-card">
                      <div className="pillar-name">{pillar.name}</div>
                      <div className="pillar-desc">{pillar.description}</div>
                      {pillar.scene_source && <div className="growth-scene-source">取材：{pillar.scene_source}</div>}
                    </div>
                  ))}
                </div>
              )}
              {contentModel?.traffic_hooks && contentModel.traffic_hooks.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">流量钩子</div>
                  {renderTextList(contentModel.traffic_hooks)}
                </div>
              )}
              {contentModel?.interaction_triggers && contentModel.interaction_triggers.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">评论触发点</div>
                  {renderTextList(contentModel.interaction_triggers)}
                </div>
              )}
            </div>
          )}

          {(onCameraStrategy?.recommended_roles || onCameraStrategy?.light_persona || onCameraStrategy?.persona_boundaries) && (
            <div className="growth-section-block">
              <div className="identity-label positioning-label">出镜策略</div>
              {onCameraStrategy?.recommended_roles && onCameraStrategy.recommended_roles.length > 0 && (
                <div className="growth-role-grid">
                  {onCameraStrategy.recommended_roles.map((item) => (
                    <div key={`${item.role}-${item.responsibility}`} className="strategy-item">
                      <div className="growth-role-name">{item.role}</div>
                      <div className="strategy-value"><strong>作用：</strong>{item.responsibility}</div>
                      <div className="strategy-value"><strong>表达：</strong>{item.expression_style}</div>
                    </div>
                  ))}
                </div>
              )}
              {onCameraStrategy?.light_persona && (
                <div className="bio-block growth-inline-block">
                  <div className="identity-label">轻人设识别点</div>
                  <div className="bio-text">{onCameraStrategy.light_persona}</div>
                </div>
              )}
              {onCameraStrategy?.persona_boundaries && onCameraStrategy.persona_boundaries.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">边界提醒</div>
                  {renderTextList(onCameraStrategy.persona_boundaries)}
                </div>
              )}
            </div>
          )}

          {(conversionPath?.traffic_to_trust || conversionPath?.trust_to_visit || conversionPath?.soft_cta_templates || conversionPath?.hard_sell_boundaries) && (
            <div className="growth-section-block">
              <div className="identity-label positioning-label">转化承接</div>
              <div className="strategy-grid">
                {conversionPath?.traffic_to_trust && (
                  <div className="strategy-item">
                    <div className="identity-label">流量如何转信任</div>
                    <div className="strategy-value">{conversionPath.traffic_to_trust}</div>
                  </div>
                )}
                {conversionPath?.trust_to_visit && (
                  <div className="strategy-item">
                    <div className="identity-label">信任如何转到店</div>
                    <div className="strategy-value">{conversionPath.trust_to_visit}</div>
                  </div>
                )}
              </div>
              {conversionPath?.soft_cta_templates && conversionPath.soft_cta_templates.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">软性 CTA</div>
                  {renderTextList(conversionPath.soft_cta_templates)}
                </div>
              )}
              {conversionPath?.hard_sell_boundaries && conversionPath.hard_sell_boundaries.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">不要硬卖的边界</div>
                  {renderTextList(conversionPath.hard_sell_boundaries)}
                </div>
              )}
            </div>
          )}

          {(executionRules?.posting_frequency || executionRules?.best_posting_times || executionRules?.batch_shoot_scenes || executionRules?.must_capture_elements || executionRules?.quality_checklist) && (
            <div className="growth-section-block">
              <div className="identity-label positioning-label">执行规则</div>
              <div className="strategy-grid">
                {executionRules?.posting_frequency && (
                  <div className="strategy-item">
                    <div className="identity-label">发布频率</div>
                    <div className="strategy-value">{executionRules.posting_frequency}</div>
                  </div>
                )}
                {executionRules?.best_posting_times && executionRules.best_posting_times.length > 0 && (
                  <div className="strategy-item">
                    <div className="identity-label">建议发布时间</div>
                    <div className="strategy-value">{executionRules.best_posting_times.join('、')}</div>
                  </div>
                )}
              </div>
              {executionRules?.batch_shoot_scenes && executionRules.batch_shoot_scenes.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">适合连拍的场景</div>
                  {renderTextList(executionRules.batch_shoot_scenes)}
                </div>
              )}
              {executionRules?.must_capture_elements && executionRules.must_capture_elements.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">每次拍摄尽量抓到</div>
                  {renderTextList(executionRules.must_capture_elements)}
                </div>
              )}
              {executionRules?.quality_checklist && executionRules.quality_checklist.length > 0 && (
                <div className="growth-sub-block">
                  <div className="identity-label">质量检查清单</div>
                  {renderTextList(executionRules.quality_checklist)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {isRegenerating && (
        <div className="detail-positioning-overlay">
          <span className="detail-positioning-overlay-badge">
            <Loader2 size={14} className="spin-icon" /> 重新生成定位中
          </span>
        </div>
      )}
    </div>
  );
}
