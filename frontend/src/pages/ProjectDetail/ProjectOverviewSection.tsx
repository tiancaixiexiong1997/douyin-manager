import { Link } from 'react-router-dom';
import { ArrowLeft, Calendar, Loader2, Pencil, Sparkles } from '../../components/Icons';
import type { ProjectStage } from './projectDetailShared';

type ProjectOverviewSectionProps = {
  project: {
    client_name: string;
    industry: string;
    target_audience: string;
  };
  currentStage: ProjectStage;
  hasStrategy: boolean;
  hasCalendar: boolean;
  referenceNames: string[];
  referenceScopeItems: string[];
  isGenerateStrategyPending: boolean;
  isRegenerateCalendarPending: boolean;
  onGenerateStrategy: () => void;
  onGenerateCalendar: () => void;
  onEditProject: () => void;
};

function getStageBadgeClass(currentStage: ProjectStage): string {
  if (currentStage === 'completed') return 'badge-green';
  if (currentStage === 'strategy_completed') return 'badge-blue';
  if (currentStage === 'strategy_generating' || currentStage === 'calendar_generating') return 'badge-yellow';
  return 'badge-purple';
}

function getStageLabel(currentStage: ProjectStage): string {
  if (currentStage === 'completed') return '已完成';
  if (currentStage === 'strategy_completed') return '定位已完成';
  if (currentStage === 'strategy_generating') return '定位生成中...';
  if (currentStage === 'calendar_generating') return '日历生成中...';
  return '草稿';
}

export function ProjectOverviewSection({
  project,
  currentStage,
  hasStrategy,
  hasCalendar,
  referenceNames,
  referenceScopeItems,
  isGenerateStrategyPending,
  isRegenerateCalendarPending,
  onGenerateStrategy,
  onGenerateCalendar,
  onEditProject,
}: ProjectOverviewSectionProps) {
  return (
    <>
      <div className="detail-breadcrumb">
        <Link to="/planning" className="btn btn-ghost btn-sm">
          <ArrowLeft size={14} /> 返回列表
        </Link>
        <span className={`badge ${getStageBadgeClass(currentStage)}`}>
          {getStageLabel(currentStage)}
        </span>
      </div>

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
            <button className="btn btn-primary btn-sm" onClick={onGenerateStrategy} disabled={isGenerateStrategyPending}>
              <Sparkles size={13} /> {isGenerateStrategyPending ? '生成中...' : '生成账号定位方案'}
            </button>
          )}
          {(currentStage === 'strategy_completed' || (hasStrategy && !hasCalendar && currentStage !== 'calendar_generating')) && (
            <button
              className="btn btn-primary btn-sm"
              onClick={onGenerateCalendar}
              disabled={isRegenerateCalendarPending}
            >
              <Calendar size={13} /> {isRegenerateCalendarPending ? '生成中...' : '生成30天日历'}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={onEditProject}>
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
            <button className="btn btn-primary" onClick={onGenerateStrategy} disabled={isGenerateStrategyPending}>
              <Sparkles size={14} /> {isGenerateStrategyPending ? '生成中...' : '开始生成账号定位方案'}
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
    </>
  );
}
