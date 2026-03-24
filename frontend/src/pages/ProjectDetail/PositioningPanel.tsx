import type { AccountPlan } from '../../api/client';
import { ChevronDown, ChevronUp, Loader2, Pencil, RefreshCw } from '../../components/Icons';
import type { ProjectStage } from './projectDetailShared';

type PositioningPanelProps = {
  positioning: NonNullable<AccountPlan['account_positioning']>;
  strategy?: AccountPlan['content_strategy'];
  currentStage: ProjectStage;
  isExpanded: boolean;
  isRegenerating: boolean;
  isRegeneratePending: boolean;
  onToggleExpand: () => void;
  onRegenerate: () => void;
  onEdit: () => void;
};

export function PositioningPanel({
  positioning,
  strategy,
  currentStage,
  isExpanded,
  isRegenerating,
  isRegeneratePending,
  onToggleExpand,
  onRegenerate,
  onEdit,
}: PositioningPanelProps) {
  return (
    <div className={`card detail-section detail-positioning ${isRegenerating ? 'detail-positioning-regenerating' : ''}`}>
      <div
        className={`detail-section-head ${isExpanded ? 'is-open' : ''}`}
        onClick={onToggleExpand}
      >
        <h2 className="section-title detail-section-title">账号定位方案</h2>
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
          {positioning.core_identity && (
            <div className="identity-block">
              <div className="identity-label">核心定位 slogan</div>
              <div className="identity-value gradient-text">{positioning.core_identity}</div>
            </div>
          )}

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

          {positioning.personality_tags && (
            <div className="positioning-block">
              <div className="identity-label positioning-label">人设标签</div>
              <div className="positioning-tags">
                {positioning.personality_tags.map((tag) => (
                  <span key={tag} className="badge badge-purple">{tag}</span>
                ))}
              </div>
            </div>
          )}

          {positioning.content_pillars && (
            <div className="positioning-block">
              <div className="identity-label positioning-label">内容支柱</div>
              <div className="pillars-grid">
                {positioning.content_pillars.map((pillar) => (
                  <div key={pillar.name} className="pillar-card">
                    <div className="pillar-name">{pillar.name}</div>
                    <div className="pillar-ratio">{pillar.ratio}</div>
                    <div className="pillar-desc">{pillar.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

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
