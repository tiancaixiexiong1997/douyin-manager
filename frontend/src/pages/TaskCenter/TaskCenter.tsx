import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { authApi, logApi, taskApi, type TaskCenterQueryParams } from '../../api/client';
import { Clock, RefreshCw, CheckCircle, AlertTriangle, ArrowRight, FileText, X } from 'lucide-react';
import './TaskCenter.css';

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '执行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
] as const;
type TaskStatusFilter = '' | NonNullable<TaskCenterQueryParams['status']>;

const TASK_TYPE_LABELS: Record<string, string> = {
  blogger_collect: '博主采集',
  blogger_viral_profile: '博主爆款归因',
  planning_generate: '账号策划生成',
  planning_calendar: '日历重生成',
  script_extraction: '脚本拆解',
};

const LOG_PAGE_SIZE_OPTIONS = [20, 50, 100] as const;

const ACTION_LABELS: Record<string, string> = {
  'download.parse': '解析下载链接',
  'download.proxy': '代理下载视频',
  'planning.create': '新建策划项目',
  'planning.delete': '删除策划项目',
  'planning.enqueue_failed': '策划任务入队失败',
  'planning.generate_script': '生成单条脚本',
  'planning.performance.create': '新增发布回流',
  'planning.performance.delete': '删除发布回流',
  'planning.performance.update': '更新发布回流',
  'planning.performance_recap.generate': '生成AI复盘',
  'planning.next_topic_batch.generate': '生成下一批选题',
  'planning.next_topic_batch.import': '导入选题到日历',
  'planning.regenerate_calendar': '重生成 30 天日历',
  'planning.retry': '重试策划生成',
  'planning.update': '更新策划信息',
  'planning.update_content_item': '更新日历条目',
  'planning.update_homepage': '更新账号主页链接',
  'blogger.viral_profile.generate': '生成博主爆款归因',
  'schedule.create': '新增日历排期',
  'schedule.delete': '删除日历排期',
  'schedule.update': '更新日历排期',
  'script.completed': '脚本拆解完成',
  'script.create': '创建脚本拆解任务',
  'script.delete': '删除脚本拆解任务',
  'script.enqueue_failed': '脚本任务入队失败',
  'script.failed': '脚本拆解失败',
  'script.retry': '重试脚本拆解',
  'script.retry.scheduled': '脚本拆解加入重试队列',
  'user.batch_delete': '批量删除用户',
  'user.batch_status': '批量修改用户状态',
  'user.create': '创建用户',
  'user.delete': '删除用户',
  'user.reset_password': '重置用户密码',
  'user.update': '更新用户',
};

const ENTITY_LABELS: Record<string, string> = {
  planning_project: '账号策划项目',
  script_extraction: '脚本拆解任务',
  content_item: '内容日历条目',
  user: '系统用户',
  video: '视频资源',
};

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function toActionLabel(action: string): string {
  return ACTION_LABELS[action] || action;
}

function toEntityLabel(entityType: string): string {
  return ENTITY_LABELS[entityType] || entityType;
}

function mapEntityLink(entityType: string, entityId: string): string {
  if (entityType === 'blogger') return '/bloggers';
  if (entityType === 'planning_project') return `/planning/${entityId}`;
  if (entityType === 'script_extraction') return '/script-extraction';
  return '/';
}

export default function TaskCenter() {
  const [status, setStatus] = useState<TaskStatusFilter>('');
  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState(false);
  const [logPage, setLogPage] = useState(1);
  const [logPageSize, setLogPageSize] = useState<number>(50);
  const [logActor, setLogActor] = useState('');
  const [logAction, setLogAction] = useState('');
  const debouncedLogActor = useDebouncedValue(logActor.trim(), 300);
  const debouncedLogAction = useDebouncedValue(logAction.trim(), 300);

  const { data: me } = useQuery({
    queryKey: ['auth-me'],
    queryFn: () => authApi.me(),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
  const isAdmin = me?.role === 'admin';

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['task-center', status],
    queryFn: () => taskApi.list({ status: status || undefined, limit: 100 }),
    refetchInterval: 5000,
  });
  const {
    data: logsPage,
    isLoading: isLogsLoading,
    isFetching: isLogsFetching,
    isError: isLogsError,
    error: logsError,
    refetch: refetchLogs,
  } = useQuery({
    queryKey: ['task-center-logs', logPage, logPageSize, debouncedLogActor, debouncedLogAction],
    queryFn: () =>
      logApi.listPaged({
        skip: (logPage - 1) * logPageSize,
        limit: logPageSize,
        actor: debouncedLogActor || undefined,
        action: debouncedLogAction || undefined,
      }),
    enabled: isAdmin && isLogDrawerOpen,
    refetchInterval: isLogDrawerOpen ? 10000 : false,
  });

  const items = data?.items ?? [];
  const summary = data?.summary ?? {};
  const runningCount = summary.running || 0;
  const queuedCount = summary.queued || 0;
  const failedCount = summary.failed || 0;
  const completedCount = summary.completed || 0;
  const latestUpdatedAt = items[0]?.updated_at
    ? new Date(items[0].updated_at).toLocaleString('zh-CN')
    : '';
  const logItems = logsPage?.items ?? [];
  const logTotal = logsPage?.total ?? 0;
  const logTotalPages = Math.max(1, Math.ceil(logTotal / logPageSize));

  useEffect(() => {
    if (!isLogDrawerOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [isLogDrawerOpen]);

  return (
    <div className="task-page animate-fade-in">
      <section className="task-hero">
        <div className="task-hero-pill"><RefreshCw size={13} /> Unified Task Hub</div>
        <h1>统一任务中心</h1>
        <p>集中查看博主采集、策划生成、脚本拆解进度与异常，不再分散在各个页面。</p>
      </section>

      <section className="task-kpi-grid">
        <div className="task-kpi-card">
          <span>执行中</span>
          <strong>{runningCount}</strong>
        </div>
        <div className="task-kpi-card">
          <span>排队中</span>
          <strong>{queuedCount}</strong>
        </div>
        <div className="task-kpi-card">
          <span>已完成</span>
          <strong>{completedCount}</strong>
        </div>
        <div className="task-kpi-card">
          <span>失败</span>
          <strong>{failedCount}</strong>
        </div>
      </section>

      <section className="card task-list-card">
        <div className="task-list-head">
          <div className="task-list-filters">
            <select
              className="form-input task-filter"
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatusFilter)}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button className="btn btn-ghost btn-sm" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw size={14} /> 刷新
            </button>
            {isAdmin && (
              <button className="btn btn-ghost btn-sm" onClick={() => setIsLogDrawerOpen(true)}>
                <FileText size={14} /> 操作日志
              </button>
            )}
          </div>
          <div className="task-list-meta">最近更新时间：{latestUpdatedAt || '暂无数据'}</div>
        </div>

        {isLoading ? (
          <div className="task-empty">加载任务中...</div>
        ) : items.length === 0 ? (
          <div className="task-empty">暂无任务记录</div>
        ) : (
          <div className="task-list">
            {items.map((item) => {
              const statusClass = `task-status task-status-${item.status}`;
              const statusText = item.status === 'queued'
                ? '排队中'
                : item.status === 'running'
                  ? '执行中'
                  : item.status === 'completed'
                    ? '已完成'
                    : item.status === 'failed'
                      ? '失败'
                      : '已取消';
              const Icon = item.status === 'completed' ? CheckCircle : item.status === 'failed' ? AlertTriangle : Clock;
              const link = mapEntityLink(item.entity_type, item.entity_id);
              return (
                <div className="task-item" key={item.id}>
                  <div className="task-item-left">
                    <div className={statusClass}><Icon size={14} /> {statusText}</div>
                    <div className="task-item-main">
                      <div className="task-item-title">{item.title}</div>
                      <div className="task-item-sub">
                        {TASK_TYPE_LABELS[item.task_type] || item.task_type}
                        <span>·</span>
                        {item.message || item.progress_step || '处理中'}
                      </div>
                      {item.error_message && (
                        <div className="task-item-error">{item.error_message}</div>
                      )}
                    </div>
                  </div>
                  <div className="task-item-right">
                    <div className="task-item-time">{new Date(item.updated_at).toLocaleString('zh-CN')}</div>
                    <Link to={link} className="task-item-link">
                      查看详情 <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {isAdmin && isLogDrawerOpen && (
        <>
          <button
            type="button"
            className="task-log-backdrop"
            aria-label="关闭操作日志抽屉"
            onClick={() => setIsLogDrawerOpen(false)}
          />
          <aside className="task-log-drawer">
            <div className="task-log-head">
              <div>
                <div className="task-log-title">操作日志</div>
                <div className="task-log-subtitle">管理员审计视图（默认隐藏在任务中心内）</div>
              </div>
              <button className="btn btn-icon btn-ghost" onClick={() => setIsLogDrawerOpen(false)}>
                <X size={16} />
              </button>
            </div>

            <div className="task-log-filters">
              <input
                className="form-input"
                placeholder="操作人（如：admin）"
                value={logActor}
                onChange={(e) => {
                  setLogActor(e.target.value);
                  setLogPage(1);
                }}
              />
              <input
                className="form-input"
                placeholder="动作代码（如：user.create）"
                value={logAction}
                onChange={(e) => {
                  setLogAction(e.target.value);
                  setLogPage(1);
                }}
              />
              <div className="task-log-filters-row">
                <select
                  className="form-input task-log-page-size"
                  value={logPageSize}
                  onChange={(e) => {
                    setLogPageSize(Number(e.target.value));
                    setLogPage(1);
                  }}
                >
                  {LOG_PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      每页 {size} 条
                    </option>
                  ))}
                </select>
                <button className="btn btn-ghost btn-sm" onClick={() => refetchLogs()} disabled={isLogsFetching}>
                  <RefreshCw size={14} /> 刷新
                </button>
                <span className="task-log-total">共 {logTotal} 条</span>
                <div className="task-log-inline-pager">
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={logPage <= 1 || isLogsFetching}
                    onClick={() => setLogPage((prev) => Math.max(1, prev - 1))}
                  >
                    上一页
                  </button>
                  <span className="task-log-page-indicator">第 {logPage} / {logTotalPages} 页</span>
                  <button
                    className="btn btn-ghost btn-sm"
                    disabled={logPage >= logTotalPages || isLogsFetching}
                    onClick={() => setLogPage((prev) => Math.min(logTotalPages, prev + 1))}
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>

            <div className="task-log-body">
              {isLogsLoading ? (
                <div className="task-log-empty">日志加载中...</div>
              ) : isLogsError ? (
                <div className="task-log-empty">加载失败：{(logsError as Error).message}</div>
              ) : logItems.length === 0 ? (
                <div className="task-log-empty">暂无日志</div>
              ) : (
                <div className="task-log-list">
                  {logItems.map((item) => (
                    <article className="task-log-item" key={item.id}>
                      <div className="task-log-item-head">
                        <span className="task-log-action">{toActionLabel(item.action)}</span>
                        <span className="task-log-time">{new Date(item.created_at).toLocaleString('zh-CN')}</span>
                      </div>
                      <div className="task-log-item-meta">
                        <span>{toEntityLabel(item.entity_type)}</span>
                        <span>·</span>
                        <span>{item.entity_id ? item.entity_id.slice(0, 8) : '无对象 ID'}</span>
                        <span>·</span>
                        <span>操作人：{item.actor}</span>
                      </div>
                      <div className="task-log-item-detail">{item.detail || '无补充说明'}</div>
                      <div className="task-log-item-subcode">{item.action} · {item.entity_type}</div>
                    </article>
                  ))}
                </div>
              )}
            </div>

          </aside>
        </>
      )}
    </div>
  );
}
