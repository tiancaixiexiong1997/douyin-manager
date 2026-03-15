import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Filter, RefreshCw } from 'lucide-react';

import { logApi } from '../../api/client';
import './OperationLogs.css';

const DEFAULT_PAGE_SIZE = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100, 200];
const SEARCH_DEBOUNCE_MS = 300;

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
  'planning.update_content_item': '更新日历内容条目',
  'planning.update_homepage': '更新账号主页链接',
  'schedule.create': '新增日历排期',
  'schedule.delete': '删除日历排期',
  'schedule.update': '更新日历排期',
  'script.completed': '脚本拆解完成',
  'script.create': '创建脚本拆解任务',
  'script.delete': '删除脚本拆解任务',
  'script.enqueue_failed': '脚本任务入队失败',
  'script.failed': '脚本拆解失败',
  'script.retry': '重试脚本拆解',
  'script.retry.scheduled': '脚本拆解已加入重试队列',
  'user.batch_delete': '批量删除用户',
  'user.batch_status': '批量修改用户状态',
  'user.create': '创建用户',
  'user.delete': '删除用户',
  'user.reset_password': '重置用户密码',
  'user.update': '更新用户权限',
};

const ENTITY_LABELS: Record<string, string> = {
  planning_project: '账号策划项目',
  script_extraction: '脚本拆解任务',
  content_item: '内容日历条目',
  user: '系统用户',
  video: '视频资源',
};

const ACTION_SCOPE_LABELS: Record<string, string> = {
  planning: '账号策划',
  script: '脚本拆解',
  schedule: '日历排期',
  user: '用户管理',
  download: '下载服务',
};

const ACTION_VERB_LABELS: Record<string, string> = {
  create: '创建',
  update: '更新',
  delete: '删除',
  retry: '重试',
  completed: '完成',
  failed: '失败',
  enqueue_failed: '入队失败',
};

function toActionLabel(action: string): string {
  if (ACTION_LABELS[action]) return ACTION_LABELS[action];
  const [scope, ...restParts] = action.split('.');
  const scopeLabel = ACTION_SCOPE_LABELS[scope] || scope;
  const rest = restParts.join('.');
  const restLabel = ACTION_VERB_LABELS[rest] || rest;
  return `${scopeLabel} · ${restLabel}`;
}

function toEntityLabel(entityType: string): string {
  return ENTITY_LABELS[entityType] || entityType;
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function OperationLogs() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [jumpPageInput, setJumpPageInput] = useState('');
  const [actor, setActor] = useState('');
  const [action, setAction] = useState('');
  const debouncedActor = useDebouncedValue(actor.trim(), SEARCH_DEBOUNCE_MS);
  const debouncedAction = useDebouncedValue(action.trim(), SEARCH_DEBOUNCE_MS);

  const { data: logsPage, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['operation-logs', page, pageSize, debouncedActor, debouncedAction],
    queryFn: () => logApi.listPaged({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      actor: debouncedActor || undefined,
      action: debouncedAction || undefined,
    }),
  });
  const logs = useMemo(() => logsPage?.items ?? [], [logsPage?.items]);
  const total = logsPage?.total ?? logs.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasPrevPage = page > 1;
  const hasNextPage = page < totalPages;
  const hasActiveFilters = !!actor.trim() || !!action.trim();

  const stats = useMemo(() => {
    const pageCount = logs.length;
    const users = new Set(logs.map((item) => item.actor)).size;
    const actions = new Set(logs.map((item) => item.action)).size;
    return { pageCount, users, actions };
  }, [logs]);

  const handleJumpPage = () => {
    const next = Number.parseInt(jumpPageInput, 10);
    if (!Number.isFinite(next)) return;
    const clamped = Math.min(totalPages, Math.max(1, next));
    setPage(clamped);
    setJumpPageInput('');
  };

  return (
    <div className="logs-page">
      <section className="logs-hero">
        <div>
          <div className="logs-hero-pill"><Activity size={13} /> 操作审计</div>
          <h1>系统操作日志</h1>
          <p>查看关键操作留痕，快速定位谁在什么时候执行了什么动作。</p>
        </div>
        <button className="btn btn-ghost" onClick={() => refetch()} disabled={isFetching}>
          <RefreshCw size={14} className={isFetching ? 'spin-icon' : ''} /> 刷新
        </button>
      </section>

      <section className="logs-stats">
        <div className="logs-stat"><span>总日志条数</span><strong>{total}</strong></div>
        <div className="logs-stat"><span>当前页条数</span><strong>{stats.pageCount}</strong></div>
        <div className="logs-stat"><span>当前页操作人</span><strong>{stats.users}</strong></div>
        <div className="logs-stat"><span>当前页动作类型</span><strong>{stats.actions}</strong></div>
      </section>

      <section className="logs-filters card">
        <div className="logs-filter-title"><Filter size={14} /> 筛选条件</div>
        <div className="logs-filter-grid">
          <input
            className="form-input"
            placeholder="按操作人模糊筛选（如：admin）"
            value={actor}
            onChange={(e) => {
              setActor(e.target.value);
              setPage(1);
            }}
          />
          <input
            className="form-input"
            placeholder="按动作代码筛选（如：user.create）"
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(1);
            }}
          />
        </div>
      </section>

      <section className="logs-table card">
        {isLoading ? (
          <div className="loading">日志加载中...</div>
        ) : logs.length === 0 ? (
          <div className="loading">{hasActiveFilters ? '暂无匹配日志' : '暂无日志'}</div>
        ) : (
          <div className="logs-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>动作</th>
                  <th>对象</th>
                  <th>操作人</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.created_at).toLocaleString('zh-CN')}</td>
                    <td>
                      <span className="logs-action" title={item.action}>{toActionLabel(item.action)}</span>
                      <div className="logs-subcode">{item.action}</div>
                    </td>
                    <td>
                      <div>{toEntityLabel(item.entity_type)}</div>
                      <div className="logs-subcode">
                        {item.entity_type}
                        {item.entity_id ? ` · ${item.entity_id.slice(0, 8)}` : ''}
                      </div>
                    </td>
                    <td>{item.actor}</td>
                    <td title={item.detail || ''}>{item.detail || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {total > 0 && totalPages > 1 && (
        <section className="logs-pagination card">
          <div className="logs-pagination-meta">
            第 {page} / {totalPages} 页 · 共 {total} 条日志
          </div>
          <div className="logs-pagination-actions">
            <select
              className="form-input logs-page-size"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  每页 {size} 条
                </option>
              ))}
            </select>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!hasPrevPage || isFetching}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              上一页
            </button>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!hasNextPage || isFetching}
              onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            >
              下一页
            </button>
            <input
              className="form-input logs-page-jump"
              value={jumpPageInput}
              onChange={(e) => setJumpPageInput(e.target.value.replace(/[^\d]/g, ''))}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleJumpPage();
              }}
              placeholder="页码"
            />
            <button
              className="btn btn-ghost btn-sm"
              disabled={!jumpPageInput || isFetching}
              onClick={handleJumpPage}
            >
              跳转
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
