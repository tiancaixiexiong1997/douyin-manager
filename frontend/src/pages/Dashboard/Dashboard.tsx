import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { bloggerApi, planningApi, scheduleApi, taskApi, type ScheduleEntry } from '../../api/client';
import {
  Users,
  Sparkles,
  FileText,
  TrendingUp,
  ArrowRight,
  Clock,
  CheckCircle,
  Download,
  RefreshCw,
  Calendar,
} from '../../components/Icons';
import { formatBackendDate, toBackendTimestamp } from '../../utils/datetime';
import './Dashboard.css';

function toSafeTimestamp(value?: string | null): number {
  return toBackendTimestamp(value);
}

function formatDateLabel(value?: string | null): string {
  return formatBackendDate(value, { month: '2-digit', day: '2-digit' }, '--');
}

function inferProjectStage(project: {
  status: string;
  account_plan?: {
    account_positioning?: unknown;
    content_strategy?: unknown;
    calendar_generation_meta?: unknown;
  } | null;
}): 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed' {
  const hasStrategy = Boolean(project.account_plan?.account_positioning || project.account_plan?.content_strategy);
  const hasCalendar = Boolean(project.account_plan?.calendar_generation_meta);
  if (project.status === 'strategy_generating') return 'strategy_generating';
  if (project.status === 'strategy_completed') return 'strategy_completed';
  if (project.status === 'calendar_generating') return 'calendar_generating';
  if (project.status === 'completed') return 'completed';
  if (project.status === 'in_progress') {
    return hasStrategy && hasCalendar ? 'calendar_generating' : 'strategy_generating';
  }
  return hasStrategy ? (hasCalendar ? 'completed' : 'strategy_completed') : 'draft';
}

export default function Dashboard() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const in30Days = new Date(today);
  in30Days.setDate(in30Days.getDate() + 29);
  const in7Days = new Date(today);
  in7Days.setDate(in7Days.getDate() + 6);
  const toDateKey = (date: Date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };
  const future30Start = toDateKey(today);
  const future30End = toDateKey(in30Days);

  const { data: bloggers = [] } = useQuery({
    queryKey: ['bloggers'],
    queryFn: () => bloggerApi.list(),
  });

  const { data: projects = [] } = useQuery({
    queryKey: ['planning-projects'],
    queryFn: () => planningApi.list(),
  });
  const { data: schedules = [], isLoading: isScheduleLoading } = useQuery({
    queryKey: ['dashboard-schedules', future30Start, future30End],
    queryFn: () =>
      scheduleApi.list({
        start_date: future30Start,
        end_date: future30End,
        limit: 2000,
      }),
  });
  const { data: taskCenter } = useQuery({
    queryKey: ['task-center-summary'],
    queryFn: () => taskApi.list({ limit: 1 }),
    refetchInterval: 5000,
  });

  const completedProjects = projects.filter((p) => inferProjectStage(p) === 'completed');
  const runningTasks = taskCenter?.summary?.running ?? 0;
  const queuedTasks = taskCenter?.summary?.queued ?? 0;
  const analyzedBloggers = bloggers.filter(b => b.is_analyzed);
  const unAnalyzedCount = bloggers.length - analyzedBloggers.length;
  const completionRate = projects.length > 0 ? Math.round((completedProjects.length / projects.length) * 100) : 0;
  const analysisRate = bloggers.length > 0 ? Math.round((analyzedBloggers.length / bloggers.length) * 100) : 0;

  const sortedProjects = [...projects].sort(
    (a, b) => toSafeTimestamp(b.updated_at) - toSafeTimestamp(a.updated_at),
  );
  const sortedBloggers = [...bloggers].sort(
    (a, b) => toSafeTimestamp(b.updated_at) - toSafeTimestamp(a.updated_at),
  );

  const stats = [
    {
      label: 'IP 资产',
      value: bloggers.length,
      sub: `${analyzedBloggers.length} 已深度分析`,
      progress: analysisRate,
      icon: Users,
      tone: 'indigo',
      link: '/bloggers',
    },
    {
      label: '策划项目',
      value: projects.length,
      sub: `${completedProjects.length} 已完成`,
      progress: completionRate,
      icon: Sparkles,
      tone: 'cyan',
      link: '/planning',
    },
    {
      label: '进行中任务',
      value: runningTasks + queuedTasks,
      sub: `${runningTasks} 执行中 / ${queuedTasks} 排队中`,
      progress: Math.min(100, (runningTasks + queuedTasks) * 10),
      icon: Clock,
      tone: 'amber',
      link: '/tasks',
    },
    {
      label: '系统效率',
      value: `${Math.min(99, Math.round((completionRate * 0.6) + (analysisRate * 0.4)))}%`,
      sub: `${unAnalyzedCount} 个博主待分析`,
      progress: Math.min(99, Math.round((completionRate * 0.6) + (analysisRate * 0.4))),
      icon: TrendingUp,
      tone: 'emerald',
      link: '/planning',
    },
  ];

  const activityFeed = [
    ...sortedProjects.slice(0, 3).map((p) => ({
      id: `project-${p.id}`,
      title: `项目「${p.client_name}」状态更新`,
      desc: inferProjectStage(p) === 'completed'
        ? '30 天日历已完成，可进入详情复查'
        : inferProjectStage(p) === 'strategy_completed'
          ? '增长策略已完成，等待生成 30 天日历'
          : inferProjectStage(p) === 'strategy_generating'
            ? 'AI 正在生成实体店增长策划'
            : inferProjectStage(p) === 'calendar_generating'
              ? 'AI 正在生成 30 天日历'
              : '项目处于草稿阶段',
      time: p.updated_at,
      link: `/planning/${p.id}`,
      type: 'project',
    })),
    ...sortedBloggers.slice(0, 3).map((b) => ({
      id: `blogger-${b.id}`,
      title: `博主「${b.nickname}」已入库`,
      desc: b.is_analyzed ? '画像分析已完成' : '等待 AI 自动分析',
      time: b.updated_at,
      link: '/bloggers',
      type: 'blogger',
    })),
  ]
    .sort((a, b) => toSafeTimestamp(b.time) - toSafeTimestamp(a.time))
    .slice(0, 6);

  const formatFollower = (count: number) => (count >= 10000 ? `${(count / 10000).toFixed(1)}w` : `${count}`);
  const formatScheduleDate = (dateKey: string) =>
    new Date(`${dateKey}T00:00:00`).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', weekday: 'short' });

  const sortedSchedules = [...schedules].sort(
    (a, b) => a.schedule_date.localeCompare(b.schedule_date) || Number(a.done) - Number(b.done) || a.created_at.localeCompare(b.created_at)
  );
  const scheduleTodayCount = schedules.filter((entry) => entry.schedule_date === future30Start).length;
  const scheduleWeekPendingCount = schedules.filter((entry) => !entry.done && entry.schedule_date <= toDateKey(in7Days)).length;
  const scheduleDoneCount = schedules.filter((entry) => entry.done).length;

  const groupedUpcomingSchedules = sortedSchedules.reduce<Array<{ dateKey: string; entries: ScheduleEntry[] }>>((acc, entry) => {
    const last = acc[acc.length - 1];
    if (!last || last.dateKey !== entry.schedule_date) {
      acc.push({ dateKey: entry.schedule_date, entries: [entry] });
    } else {
      last.entries.push(entry);
    }
    return acc;
  }, []);

  return (
    <div className="dashboard-shell animate-fade-in">
      <section className="dash-hero">
        <div className="dash-hero-content">
          <div className="dash-hero-chip">Creator Console</div>
          <h1>你的内容系统正在稳定运行</h1>
          <p>从博主洞察到策划落地，一屏追踪全链路进度与关键瓶颈。</p>
        </div>

        <div className="dash-hero-actions">
          <Link to="/bloggers" className="dash-hero-btn dash-hero-btn-light">
            <Users size={16} /> 添加对标博主
          </Link>
          <Link to="/planning" className="dash-hero-btn dash-hero-btn-solid">
            <Sparkles size={16} /> 新建策划项目
          </Link>
        </div>

        <div className="dash-quick-actions">
          <Link to="/script-extraction" className="dash-quick-card">
            <RefreshCw size={15} />
            <span>脚本拆解</span>
            <ArrowRight size={14} />
          </Link>
          <Link to="/downloader" className="dash-quick-card">
            <Download size={15} />
            <span>无水印下载</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="dash-stats-grid">
        {stats.map(({ label, value, sub, progress, icon: Icon, tone, link }) => {
          return (
            <Link to={link} key={label} className={`dash-stat-card dash-tone-${tone}`}>
              <div className="dash-stat-top">
                <span>{label}</span>
                <Icon size={20} />
              </div>
              <div className="dash-stat-value">{value}</div>
              <div className="dash-stat-sub">{sub}</div>
              <div className="dash-progress-track">
                <div className="dash-progress-bar" style={{ width: `${Math.max(8, progress)}%` }} />
              </div>
            </Link>
          );
        })}
      </section>

      <section className="dash-main-grid">
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h2>最近策划项目</h2>
            <Link to="/planning">全部项目 <ArrowRight size={13} /></Link>
          </div>

          {projects.length === 0 ? (
            <div className="dash-empty">
              <div className="dash-empty-icon"><FileText size={22} /></div>
              <div className="dash-empty-title">还没有策划项目</div>
              <div className="dash-empty-desc">从右上角创建第一个项目，系统会自动追踪状态。</div>
            </div>
          ) : (
            <div className="dash-list">
              {sortedProjects.slice(0, 3).map((p) => {
                const stage = inferProjectStage(p);
                return (
                <Link to={`/planning/${p.id}`} key={p.id} className="dash-project-item">
                  <div className="dash-project-left">
                    <div className="dash-project-avatar">
                      {p.account_avatar_url ? (
                        <img src={p.account_avatar_url} alt={p.account_nickname || p.client_name} />
                      ) : (
                        <span>{(p.account_nickname || p.client_name)[0]}</span>
                      )}
                    </div>
                    <div className="dash-project-main">
                      <div className="dash-project-name">{p.account_nickname || p.client_name}</div>
                      <div className="dash-project-meta">
                        <span className="dash-project-industry">{p.industry}</span>
                        <span className="dash-project-time">{formatDateLabel(p.updated_at)} 更新</span>
                      </div>
                    </div>
                  </div>
                  <div className="dash-project-right">
                    <span className={`badge ${
                      stage === 'completed' ? 'badge-green' :
                      stage === 'strategy_completed' ? 'badge-blue' :
                      stage === 'strategy_generating' || stage === 'calendar_generating' ? 'badge-yellow' : 'badge-purple'
                    }`}>
                      {stage === 'completed' ? '已完成' :
                       stage === 'strategy_completed' ? '策略已完成' :
                       stage === 'strategy_generating' ? '策略生成中' :
                       stage === 'calendar_generating' ? '日历生成中' : '草稿'}
                    </span>
                    <ArrowRight size={14} />
                  </div>
                </Link>
              )})}
            </div>
          )}
        </div>

        <div className="dash-panel">
          <div className="dash-panel-head">
            <h2>博主 IP 快览</h2>
            <Link to="/bloggers">进入管理 <ArrowRight size={13} /></Link>
          </div>

          {bloggers.length === 0 ? (
            <div className="dash-empty">
              <div className="dash-empty-icon"><Users size={22} /></div>
              <div className="dash-empty-title">IP 库暂无博主</div>
              <div className="dash-empty-desc">添加对标账号后，系统将自动生成风格画像。</div>
            </div>
          ) : (
            <div className="dash-list">
              {sortedBloggers.slice(0, 3).map((b) => (
                <div key={b.id} className="dash-blogger-item">
                  <div className="dash-blogger-avatar">
                    {b.avatar_url ? (
                      <img src={b.avatar_url} alt={b.nickname} />
                    ) : (
                      <span>{b.nickname[0]}</span>
                    )}
                  </div>
                  <div className="dash-blogger-main">
                    <div className="dash-blogger-name">{b.nickname}</div>
                    <div className="dash-blogger-sub">
                      {formatFollower(b.follower_count)} 粉丝 · {formatDateLabel(b.updated_at)}
                    </div>
                  </div>
                  {b.is_analyzed ? (
                    <CheckCircle size={15} className="dash-blogger-done" />
                  ) : (
                    <div className="dash-pending-dot" />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="dash-panel dash-panel-schedule">
          <div className="dash-panel-head">
            <h2>近期排期</h2>
            <Link to="/schedule">查看日历 <ArrowRight size={13} /></Link>
          </div>
          {isScheduleLoading ? (
            <div className="dash-empty">
              <div className="dash-empty-icon"><Calendar size={22} /></div>
              <div className="dash-empty-title">排期数据加载中</div>
              <div className="dash-empty-desc">正在同步未来 30 天排期，请稍候。</div>
            </div>
          ) : schedules.length === 0 ? (
            <div className="dash-empty">
              <div className="dash-empty-icon"><Calendar size={22} /></div>
              <div className="dash-empty-title">未来 30 天暂无排期</div>
              <div className="dash-empty-desc">去日历排期表添加内容后，这里会自动同步展示。</div>
            </div>
          ) : (
            <>
              <div className="dash-schedule-kpis">
                <div className="dash-schedule-kpi">
                  <span>未来30天</span>
                  <strong>{schedules.length}</strong>
                </div>
                <div className="dash-schedule-kpi">
                  <span>本周待完成</span>
                  <strong>{scheduleWeekPendingCount}</strong>
                </div>
                <div className="dash-schedule-kpi">
                  <span>今日排期</span>
                  <strong>{scheduleTodayCount}</strong>
                </div>
                <div className="dash-schedule-kpi">
                  <span>已完成</span>
                  <strong>{scheduleDoneCount}</strong>
                </div>
              </div>
              <div className="dash-schedule-list">
                {groupedUpcomingSchedules.slice(0, 5).map((group) => (
                  <div key={group.dateKey} className="dash-schedule-group">
                    <div className="dash-schedule-date">{formatScheduleDate(group.dateKey)}</div>
                    <div className="dash-schedule-items">
                      {group.entries.slice(0, 3).map((entry) => (
                        <div key={entry.id} className="dash-schedule-item">
                          <div className="dash-schedule-title">{entry.title}</div>
                          <div className="dash-schedule-sub">{entry.content_type || '未填写类型'}</div>
                          <span className={`badge ${entry.done ? 'badge-green' : 'badge-yellow'}`}>
                            {entry.done ? '已完成' : '待完成'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="dash-panel dash-panel-activity">
          <div className="dash-panel-head">
            <h2>最近动态</h2>
          </div>
          {activityFeed.length === 0 ? (
            <div className="dash-empty">
              <div className="dash-empty-icon"><Clock size={22} /></div>
              <div className="dash-empty-title">暂无动态</div>
              <div className="dash-empty-desc">当你创建项目或添加博主后，这里会自动出现更新。</div>
            </div>
          ) : (
            <div className="dash-activity-list">
              {activityFeed.map((item) => (
                <Link key={item.id} to={item.link} className="dash-activity-item">
                  <div className={`dash-activity-mark ${item.type === 'project' ? 'project' : 'blogger'}`} />
                  <div className="dash-activity-main">
                    <div className="dash-activity-title">{item.title}</div>
                    <div className="dash-activity-desc">{item.desc}</div>
                  </div>
                  <div className="dash-activity-time">{formatDateLabel(item.time)}</div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
