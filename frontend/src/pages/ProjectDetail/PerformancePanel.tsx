import { useMemo } from 'react';
import { type ContentItem, type ContentPerformance, type ContentPerformanceSummary, type NextTopicBatch, type PerformanceRecap } from '../../api/client';
import { Pencil, Plus, Sparkles, Trash2, TrendingUp } from '../../components/Icons';
import { formatBackendDateTime } from '../../utils/datetime';

function formatMetricNumber(value?: number | null): string {
  return Number(value || 0).toLocaleString('zh-CN');
}

function formatMetricPercent(value?: number | null): string {
  return value != null ? `${Number(value).toFixed(1)}%` : '-';
}

function getPerformanceEngagementRate(row: Pick<ContentPerformance, 'views' | 'likes' | 'comments' | 'shares'>): number | null {
  if (!row.views) return null;
  return ((row.likes + row.comments + row.shares) / row.views) * 100;
}

function getContentItemLabel(item?: Pick<ContentItem, 'day_number' | 'title_direction'> | null): string {
  if (!item) return '未关联策划条目';
  return `第 ${item.day_number} 天 · ${item.title_direction}`;
}

function getPerformanceHighlightMeta(
  item: ContentPerformance | null | undefined,
  kind: 'views' | 'completion' | 'engagement' | 'conversion'
): string {
  if (!item) return '暂无数据';
  if (kind === 'views') return `${formatMetricNumber(item.views)} 播放`;
  if (kind === 'completion') return item.completion_rate != null ? `${Number(item.completion_rate).toFixed(1)}% 完播率` : '暂无完播率';
  if (kind === 'engagement') {
    const rate = getPerformanceEngagementRate(item);
    return rate != null ? `${rate.toFixed(1)}% 互动率` : '暂无互动率';
  }
  if (item.conversions > 0 && item.views > 0) {
    return `${item.conversions} 转化 · ${(item.conversions / item.views * 100).toFixed(2)}% 转化率`;
  }
  if (item.conversions > 0) return `${item.conversions} 转化`;
  return '暂无转化';
}

type PerformancePanelProps = {
  contentItems: ContentItem[];
  performanceList: ContentPerformance[];
  performanceSummary?: ContentPerformanceSummary;
  performanceRecap?: PerformanceRecap;
  nextTopicBatch?: NextTopicBatch;
  isGeneratingRecap: boolean;
  generateRecapError?: Error | null;
  onGenerateRecap: () => void;
  isGeneratingNextTopics: boolean;
  generateNextTopicsError?: Error | null;
  onGenerateNextTopics: () => void;
  isImportingNextTopic: boolean;
  importNextTopicError?: Error | null;
  onImportNextTopic: (itemIndex: number) => void;
  isRemovingPerformance: boolean;
  onRemovePerformance: (performanceId: string) => void;
  onCreatePerformance: () => void;
  onEditPerformance: (row: ContentPerformance) => void;
};

export function PerformancePanel({
  contentItems,
  performanceList,
  performanceSummary,
  performanceRecap,
  nextTopicBatch,
  isGeneratingRecap,
  generateRecapError,
  onGenerateRecap,
  isGeneratingNextTopics,
  generateNextTopicsError,
  onGenerateNextTopics,
  isImportingNextTopic,
  importNextTopicError,
  onImportNextTopic,
  isRemovingPerformance,
  onRemovePerformance,
  onCreatePerformance,
  onEditPerformance,
}: PerformancePanelProps) {
  const contentItemMap = useMemo(
    () => new Map(contentItems.map((item) => [item.id, item])),
    [contentItems],
  );
  const linkedContentItemIds = new Set(
    performanceList.map((row) => row.content_item_id).filter((value): value is string => Boolean(value))
  );
  const pendingContentItems = contentItems.filter((item) => !linkedContentItemIds.has(item.id));

  return (
    <div className="card detail-section performance-section">
      <div className="detail-section-head">
        <h2 className="section-title detail-section-title flex items-center gap-2">
          <TrendingUp size={18} /> 发布后数据回流
        </h2>
        <div className="performance-head-actions">
          <button
            className="btn btn-ghost btn-sm"
            onClick={onGenerateRecap}
            disabled={isGeneratingRecap || performanceList.length === 0}
          >
            <Sparkles size={13} /> {isGeneratingRecap ? '复盘中...' : 'AI 自动复盘'}
          </button>
          <button className="btn btn-primary btn-sm" onClick={onCreatePerformance}>
            <Plus size={13} /> 新增数据
          </button>
        </div>
      </div>

      <div className="performance-overview">
        <div className="performance-kpis">
          <div className="performance-kpi">
            <span>已回流 / 计划内容</span>
            <strong>
              {performanceSummary ? `${performanceSummary.total_items}/${performanceSummary.planned_content_count}` : `0/${contentItems.length || 0}`}
            </strong>
            <em>{formatMetricPercent(performanceSummary?.coverage_rate)}</em>
          </div>
          <div className="performance-kpi">
            <span>总播放</span>
            <strong>{formatMetricNumber(performanceSummary?.total_views)}</strong>
            <em>{formatMetricNumber(performanceSummary?.total_likes)} 点赞</em>
          </div>
          <div className="performance-kpi">
            <span>平均互动率</span>
            <strong>{formatMetricPercent(performanceSummary?.avg_engagement_rate)}</strong>
            <em>{formatMetricNumber((performanceSummary?.total_comments || 0) + (performanceSummary?.total_shares || 0))} 评论+转发</em>
          </div>
          <div className="performance-kpi">
            <span>平均 5 秒完播率</span>
            <strong>{formatMetricPercent(performanceSummary?.avg_completion_5s_rate)}</strong>
            <em>整体完播率 {formatMetricPercent(performanceSummary?.avg_completion_rate)}</em>
          </div>
          <div className="performance-kpi">
            <span>总转化</span>
            <strong>{formatMetricNumber(performanceSummary?.total_conversions)}</strong>
            <em>平均转化率 {formatMetricPercent(performanceSummary?.avg_conversion_rate)}</em>
          </div>
          <div className="performance-kpi">
            <span>待补回流</span>
            <strong>{formatMetricNumber(pendingContentItems.length)}</strong>
            <em>{pendingContentItems[0] ? getContentItemLabel(pendingContentItems[0]) : '当前已全部覆盖'}</em>
          </div>
        </div>

        {performanceSummary?.insights?.length ? (
          <div className="performance-insights">
            {performanceSummary.insights.map((insight) => (
              <div key={`${insight.title}-${insight.body}`} className={`performance-insight performance-insight-${insight.tone}`}>
                <div className="performance-insight-title">{insight.title}</div>
                <p>{insight.body}</p>
              </div>
            ))}
          </div>
        ) : null}

        <div className="performance-highlights">
          <div className="performance-highlight">
            <span>最高播放</span>
            <strong>{performanceSummary?.best_view_item?.title || '暂无数据'}</strong>
            <em>{getPerformanceHighlightMeta(performanceSummary?.best_view_item, 'views')}</em>
          </div>
          <div className="performance-highlight">
            <span>最佳完播</span>
            <strong>{performanceSummary?.best_completion_item?.title || '暂无数据'}</strong>
            <em>{getPerformanceHighlightMeta(performanceSummary?.best_completion_item, 'completion')}</em>
          </div>
          <div className="performance-highlight">
            <span>最佳互动</span>
            <strong>{performanceSummary?.best_engagement_item?.title || '暂无数据'}</strong>
            <em>{getPerformanceHighlightMeta(performanceSummary?.best_engagement_item, 'engagement')}</em>
          </div>
          <div className="performance-highlight">
            <span>最佳转化</span>
            <strong>{performanceSummary?.best_conversion_item?.title || '暂无数据'}</strong>
            <em>{getPerformanceHighlightMeta(performanceSummary?.best_conversion_item, 'conversion')}</em>
          </div>
        </div>
      </div>

      <div className="performance-recap-card">
        <div className="performance-recap-head">
          <div>
            <div className="performance-recap-eyebrow">AI 复盘</div>
            <h3>下一轮内容建议</h3>
          </div>
          <div className="performance-recap-side">
            <div className="performance-recap-meta">
              {performanceRecap ? `更新于 ${formatBackendDateTime(performanceRecap.generated_at)}` : '录入回流后可一键生成'}
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={onGenerateNextTopics}
              disabled={isGeneratingNextTopics || !performanceRecap}
            >
              <Sparkles size={13} /> {isGeneratingNextTopics ? '生成中...' : '下一批10条选题'}
            </button>
          </div>
        </div>

        {generateRecapError && (
          <div className="error-tip" style={{ marginTop: 12 }}>
            {generateRecapError.message}
          </div>
        )}
        {generateNextTopicsError && (
          <div className="error-tip" style={{ marginTop: 12 }}>
            {generateNextTopicsError.message}
          </div>
        )}
        {importNextTopicError && (
          <div className="error-tip" style={{ marginTop: 12 }}>
            {importNextTopicError.message}
          </div>
        )}

        {!performanceRecap ? (
          <div className="performance-recap-empty">
            {performanceList.length === 0
              ? '先录入至少 1 条回流数据，再生成 AI 自动复盘。'
              : '已经有回流数据了，可以点击上方“AI 自动复盘”生成下一轮选题和优化建议。'}
          </div>
        ) : (
          <div className="performance-recap-body">
            <p className="performance-recap-summary">{performanceRecap.overall_summary}</p>

            <div className="performance-recap-grid">
              <div className="performance-recap-block">
                <span>继续放大</span>
                <ul>
                  {performanceRecap.winning_patterns.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div className="performance-recap-block">
                <span>优先优化</span>
                <ul>
                  {performanceRecap.optimization_focus.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div className="performance-recap-block">
                <span>风险提醒</span>
                <ul>
                  {performanceRecap.risk_alerts.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div className="performance-recap-block">
                <span>下周动作</span>
                <ul>
                  {performanceRecap.next_actions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
              <div className="performance-recap-block performance-recap-block-wide">
                <span>下一批选题方向</span>
                <ul>
                  {performanceRecap.next_topic_angles.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="performance-topic-batch-card">
        <div className="performance-topic-batch-head">
          <div>
            <div className="performance-recap-eyebrow">选题批次</div>
            <h3>基于复盘的下一批 10 条</h3>
          </div>
          <div className="performance-recap-meta">
            {nextTopicBatch ? `更新于 ${formatBackendDateTime(nextTopicBatch.generated_at)}` : '先生成 AI 复盘，再生成这一批选题'}
          </div>
        </div>

        {!nextTopicBatch ? (
          <div className="performance-recap-empty">
            {performanceRecap
              ? '可以点击上方“下一批10条选题”，快速生成一组更适合继续试跑的选题。'
              : '这一批选题会自动参考 AI 复盘中的有效模式、优化重点和风险提醒。'}
          </div>
        ) : (
          <div className="performance-topic-batch-body">
            <p className="performance-recap-summary">{nextTopicBatch.overall_strategy}</p>
            <div className="performance-topic-batch-list">
              {nextTopicBatch.items.map((item, index) => (
                <div key={`${item.title_direction}-${index}`} className="performance-topic-item">
                  <div className="performance-topic-item-head">
                    <span className="performance-topic-index">{index + 1}</span>
                    <strong>{item.title_direction}</strong>
                  </div>
                  <div className="performance-topic-tags">
                    <span className="badge badge-purple">{item.content_type}</span>
                    {item.content_pillar ? <span className="badge badge-green">{item.content_pillar}</span> : null}
                    {item.imported_day_number ? <span className="badge badge-blue">Day {item.imported_day_number}</span> : null}
                  </div>
                  {item.hook_hint ? <p className="performance-topic-copy"><strong>开头建议：</strong>{item.hook_hint}</p> : null}
                  {item.why_this_angle ? <p className="performance-topic-copy"><strong>为什么做：</strong>{item.why_this_angle}</p> : null}
                  <div className="performance-topic-actions">
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => onImportNextTopic(index)}
                      disabled={isImportingNextTopic || Boolean(item.imported_content_item_id)}
                    >
                      <Plus size={13} /> {item.imported_day_number ? `已加入 Day ${item.imported_day_number}` : '加入内容日历'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {performanceList.length === 0 ? (
        <div className="detail-calendar-empty">
          暂无回流数据，建议先补作品链接、关联策划条目，再录入播放、完播、互动和转化，复盘结论会更快稳定下来。
        </div>
      ) : (
        <div className="performance-table-wrap">
          <table className="performance-table">
            <thead>
              <tr>
                <th>关联条目</th>
                <th>标题</th>
                <th>发布日期</th>
                <th>播放</th>
                <th>互动率</th>
                <th>2秒跳出率</th>
                <th>5秒完播率</th>
                <th>完播率</th>
                <th>点赞</th>
                <th>转化</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {performanceList.map((row) => (
                <tr key={row.id}>
                  <td className="performance-linked-cell">
                    {getContentItemLabel(row.content_item_id ? contentItemMap.get(row.content_item_id) : null)}
                  </td>
                  <td>{row.title}</td>
                  <td>{row.publish_date || '-'}</td>
                  <td>{formatMetricNumber(row.views)}</td>
                  <td>{formatMetricPercent(getPerformanceEngagementRate(row))}</td>
                  <td>{row.bounce_2s_rate != null ? `${Number(row.bounce_2s_rate).toFixed(1)}%` : '-'}</td>
                  <td>{row.completion_5s_rate != null ? `${Number(row.completion_5s_rate).toFixed(1)}%` : '-'}</td>
                  <td>{row.completion_rate != null ? `${Number(row.completion_rate).toFixed(1)}%` : '-'}</td>
                  <td>{formatMetricNumber(row.likes)}</td>
                  <td>{formatMetricNumber(row.conversions)}</td>
                  <td>
                    <div className="performance-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => onEditPerformance(row)}>
                        <Pencil size={12} /> 编辑
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => onRemovePerformance(row.id)}
                        disabled={isRemovingPerformance}
                      >
                        <Trash2 size={12} /> 删除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
