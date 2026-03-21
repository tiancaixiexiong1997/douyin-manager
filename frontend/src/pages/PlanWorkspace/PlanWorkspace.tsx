import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';

import {
  planningApi,
  bloggerApi,
  type CreatePlanningRequest,
} from '../../api/client';
import { CustomSelect } from '../../components/CustomSelect';
import { Plus, X, Sparkles, ArrowRight, Clock, CheckCircle, Trash2, RefreshCw, Link as LinkIcon, Search, Filter } from '../../components/Icons';
import { formatBackendDate } from '../../utils/datetime';
import { notifyError } from '../../utils/notify';
import './PlanWorkspace.css';

const DEFAULT_PAGE_SIZE = 9;
const PAGE_SIZE_OPTIONS = [9, 18, 36];
const SEARCH_DEBOUNCE_MS = 350;
const TOTAL_CREATE_STEPS = 3;
const REQUIRED_INTAKE_FIELDS = ['client_name', 'industry', 'target_audience', 'ip_requirements'] as const;
const INTAKE_FIELD_LABELS: Record<typeof REQUIRED_INTAKE_FIELDS[number], string> = {
  client_name: '客户/品牌名称',
  industry: '行业垂类',
  target_audience: '目标受众',
  ip_requirements: '账号定位与内容支柱',
};
const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: '全部状态' },
  { value: 'draft', label: '草稿/待开始' },
  { value: 'strategy_generating', label: '定位生成中' },
  { value: 'strategy_completed', label: '定位已完成' },
  { value: 'calendar_generating', label: '日历生成中' },
  { value: 'completed', label: '已完成' },
];

type ProjectStage = 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed';

function inferProjectStage(project: {
  status: string;
  account_plan?: {
    account_positioning?: unknown;
    content_strategy?: unknown;
    calendar_generation_meta?: unknown;
  } | null;
}) {
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

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function CreatePlanModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<CreatePlanningRequest>({
    client_name: '',
    industry: '',
    target_audience: '',
    unique_advantage: '',
    ip_requirements: '',
    style_preference: '',
    business_goal: '',
    reference_blogger_ids: [],
    account_homepage_url: '',
  });
  const [rhythmPreset, setRhythmPreset] = useState<'month10' | 'month12' | 'month15'>('month10');
  const [timeWindows, setTimeWindows] = useState('19:00、21:00');
  const [goalTarget, setGoalTarget] = useState('30天发布10条，至少跑出1-2条高潜内容');
  const [iterationRule, setIterationRule] = useState('每周复盘1次，每次只调整1-2个变量（开头/标题/结构）');
  const [missingFields] = useState<string[]>([...REQUIRED_INTAKE_FIELDS]);
  const qc = useQueryClient();
  const { data: bloggers = [] } = useQuery({ queryKey: ['bloggers'], queryFn: () => bloggerApi.list() });
  const selectedReferenceBloggers = useMemo(
    () => bloggers.filter((blogger) => form.reference_blogger_ids.includes(blogger.id)),
    [bloggers, form.reference_blogger_ids]
  );
  const mutation = useMutation({
    mutationFn: planningApi.create,
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ['planning-projects'] });
      onClose();
      navigate(`/planning/${project.id}`);
    },
  });

  const stepTitleMap = useMemo(
    () => ({
      1: { title: '结构化填写', desc: '直接填写账号策划草稿，确保信息贴合真实 IP' },
      2: { title: '对标参考', desc: '选参考博主与主页，统一对标口径' },
      3: { title: '确认创建', desc: '确认信息后创建项目草稿，进入详情页继续生成定位' },
    }),
    []
  );
  const rhythmText = {
    month10: '每月10条（推荐，3天1条）',
    month12: '每月12条（2-3天1条）',
    month15: '每月15条（2天1条）',
  }[rhythmPreset];
  const requiredMissingFields = REQUIRED_INTAKE_FIELDS.filter((key) => !(form[key] || '').trim());
  const displayMissingFields = Array.from(new Set([...missingFields, ...requiredMissingFields]));
  const canGoNextStep1 = requiredMissingFields.length === 0;
  const canSubmit = canGoNextStep1 && !!goalTarget.trim() && !!timeWindows.trim();
  const nextStepLabel = step === 1 ? '进入参考 IP' : '进入生成确认';
  const buildPayload = (): CreatePlanningRequest => {
    const executionBlock = [
      '【执行策略】',
      `发布节奏：${rhythmText}`,
      `发布时间窗口：${timeWindows.trim()}`,
      `阶段目标：${goalTarget.trim()}`,
      `迭代规则：${iterationRule.trim()}`,
    ].join('\n');
    const normalizedIpRequirements = form.ip_requirements.includes('【执行策略】')
      ? form.ip_requirements.trim()
      : `${form.ip_requirements.trim()}\n\n${executionBlock}`;
    const combinedBusinessGoal = [form.business_goal?.trim(), goalTarget.trim()].filter(Boolean).join('；');
    return {
      ...form,
      client_name: form.client_name.trim(),
      industry: form.industry.trim(),
      target_audience: form.target_audience.trim(),
      unique_advantage: form.unique_advantage?.trim() || undefined,
      ip_requirements: normalizedIpRequirements,
      style_preference: form.style_preference?.trim() || undefined,
      business_goal: combinedBusinessGoal || undefined,
      account_homepage_url: form.account_homepage_url?.trim() || undefined,
    };
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal plan-modal animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="plan-modal-title-wrap">
            <h2 className="modal-title">新建账号策划项目</h2>
            <div className="step-indicator">步骤 {step} / {TOTAL_CREATE_STEPS} · {stepTitleMap[step as 1 | 2 | 3].title}</div>
            <div className="step-subtitle">{stepTitleMap[step as 1 | 2 | 3].desc}</div>
          </div>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="modal-progress">
          <div className="modal-progress-bar" style={{ width: `${(step / TOTAL_CREATE_STEPS) * 100}%` }} />
        </div>

        <div className="plan-modal-steps">
          {([1, 2, 3] as const).map((stepIndex) => (
            <div
              key={stepIndex}
              className={`plan-modal-step${stepIndex === step ? ' active' : ''}${stepIndex < step ? ' done' : ''}`}
            >
              <span className="plan-modal-step-dot">{stepIndex}</span>
              <span className="plan-modal-step-label">{stepTitleMap[stepIndex].title}</span>
            </div>
          ))}
        </div>

        <div className="plan-modal-content">

        {step === 1 && (
          <section className="plan-intake-form animate-fade-in">
              <div className="plan-intake-form-title">结构化策划草稿</div>
              <div className={`plan-intake-state ${canGoNextStep1 ? 'ready' : 'pending'}`}>
                {canGoNextStep1 ? '关键信息已补齐，可进入下一步' : `还缺 ${displayMissingFields.length} 项必填信息`}
              </div>
              {!canGoNextStep1 && (
                <div className="plan-intake-missing">
                  {displayMissingFields.map((field) => (
                    <span key={field} className="plan-intake-missing-tag">
                      {INTAKE_FIELD_LABELS[field as typeof REQUIRED_INTAKE_FIELDS[number]] || field}
                    </span>
                  ))}
                </div>
              )}
              <div className="plan-form-section">
                <div className="plan-form-section-title">基础信息</div>
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">客户/品牌名称 *</label>
                    <input className="form-input" placeholder="如：张三美妆工作室" value={form.client_name}
                      onChange={e => setForm(f => ({ ...f, client_name: e.target.value }))} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">行业垂类 *</label>
                    <input className="form-input" placeholder="如：美妆、健身、美食..." value={form.industry}
                      onChange={e => setForm(f => ({ ...f, industry: e.target.value }))} />
                  </div>
                </div>
              </div>
              <div className="plan-form-section">
                <div className="plan-form-section-title">定位草稿</div>
                <div className="form-group">
                  <label className="form-label">目标受众画像 *</label>
                  <textarea className="form-input form-textarea" placeholder="描述目标用户：如 25-35岁 职场女性，关注护肤和精致生活..."
                    value={form.target_audience}
                    onChange={e => setForm(f => ({ ...f, target_audience: e.target.value }))} />
                  <p className="form-hint">尽量写清年龄段、职业状态、现在最在意的问题，以及愿意为这类内容停留的原因。</p>
                </div>
                <div className="form-group">
                  <label className="form-label">账号定位与内容支柱 *</label>
                  <textarea
                    className="form-input form-textarea"
                    placeholder="如：专业测评+真实改造+避坑清单；内容支柱：测评/教程/答疑..."
                    value={form.ip_requirements}
                    onChange={e => setForm(f => ({ ...f, ip_requirements: e.target.value }))}
                  />
                  <p className="form-hint">写明你要解决的用户问题、主要内容支柱，以及用户为什么会关注而不是看完就走。</p>
                </div>
                <div className="form-group">
                  <label className="form-label">独特优势/亮点</label>
                  <input className="form-input" placeholder="如：有10年美妆师经验、自创护肤配方..." value={form.unique_advantage}
                    onChange={e => setForm(f => ({ ...f, unique_advantage: e.target.value }))} />
                  <p className="form-hint">这里优先写能形成信任和差异的事实，不写“真诚”“热爱”“会表达”这类空词。</p>
                </div>
              </div>
          </section>
        )}

        {step === 2 && (
          <div className="plan-reference-layout animate-fade-in">
            <section className="plan-reference-main">
              <div className="plan-form-section">
                <div className="plan-form-section-title">参考风格补充</div>
                <div className="form-group">
                  <label className="form-label">对标表达风格</label>
                  <input className="form-input" placeholder="如：轻松幽默、专业权威、温暖治愈..." value={form.style_preference}
                    onChange={e => setForm(f => ({ ...f, style_preference: e.target.value }))} />
                </div>
                <div className="form-group">
                  <label className="form-label">商业目标</label>
                  <input
                    className="form-input"
                    placeholder="如：私域引流、转化咨询、品牌曝光"
                    value={form.business_goal}
                    onChange={e => setForm(f => ({ ...f, business_goal: e.target.value }))}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">参考博主（推荐选择 3-5 个）</label>
                <div className="plan-reference-selection-summary">
                  <strong>{selectedReferenceBloggers.length}</strong>
                  <span>已选参考 IP</span>
                </div>
                <div className="plan-reference-helper">
                  这里会影响账号定位、日历选题和后续脚本的表达风格，不是直接照搬某个 IP。
                </div>
                {bloggers.length === 0 ? (
                  <div className="no-bloggers-tip">
                    IP 库暂无博主，<Link to="/bloggers" onClick={onClose}>先去添加</Link>
                  </div>
                ) : (
                  <div className="blogger-selector">
                    {bloggers.map(b => (
                      <button
                        key={b.id}
                        className={`blogger-select-item ${form.reference_blogger_ids.includes(b.id) ? 'selected' : ''}`}
                        onClick={() => setForm(f => ({
                          ...f,
                          reference_blogger_ids: f.reference_blogger_ids.includes(b.id)
                            ? f.reference_blogger_ids.filter(id => id !== b.id)
                            : [...f.reference_blogger_ids, b.id]
                        }))}
                      >
                        <div className="blogger-select-avatar">{b.nickname[0]}</div>
                        <div>
                          <div className="blogger-select-name">{b.nickname}</div>
                          <div className="blogger-select-fans">{(b.follower_count / 10000).toFixed(1)}w</div>
                        </div>
                        {form.reference_blogger_ids.includes(b.id) && (
                          <CheckCircle size={14} style={{ marginLeft: 'auto', color: 'var(--primary-500)' }} />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <aside className="plan-reference-side">
              <div className="plan-reference-side-card">
                <div className="plan-reference-side-title">已选参考 IP</div>
                <div className="plan-reference-side-subtitle">
                  当前已选择 {selectedReferenceBloggers.length} 位，建议保留 3-5 位最有代表性的参考对象。
                </div>
                {selectedReferenceBloggers.length > 0 ? (
                  <div className="plan-reference-preview-list">
                    {selectedReferenceBloggers.map((blogger) => (
                      <span key={blogger.id} className="plan-reference-chip">
                        {blogger.nickname}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="plan-reference-empty">还没选择参考 IP，可以先从最像你想做的账号开始选。</div>
                )}
              </div>

              <div className="plan-reference-side-card">
                <div className="plan-reference-side-title">
                  <LinkIcon size={13} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                  策划账号主页
                </div>
                <div className="plan-reference-side-subtitle">可选，后面也能补填。填了以后系统会同步头像、昵称和主页简介。</div>
                <input
                  className="form-input"
                  placeholder="粘贴抖音主页链接，自动抓取头像、昵称、简介..."
                  value={form.account_homepage_url || ''}
                  onChange={e => setForm(f => ({ ...f, account_homepage_url: e.target.value }))}
                />
              </div>
            </aside>
          </div>
        )}

        {step === 3 && (
          <div className="plan-final-layout animate-fade-in">
            <section className="plan-final-main">
              <div className="plan-form-section">
                <div className="plan-form-section-title">执行设置</div>
                <div className="form-group">
                  <label className="form-label">发布节奏 *</label>
                  <div className="count-options">
                    {[
                      { label: '每月10条', value: 'month10' as const },
                      { label: '每月12条', value: 'month12' as const },
                      { label: '每月15条', value: 'month15' as const },
                    ].map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`count-option${rhythmPreset === option.value ? ' active' : ''}`}
                        onClick={() => setRhythmPreset(option.value)}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                  <p className="form-hint">默认推荐每月10条（约3天1条），优先保证稳定更新与质量。</p>
                </div>
                <div className="grid-2">
                  <div className="form-group">
                    <label className="form-label">发布时间窗口 *</label>
                    <input
                      className="form-input"
                      placeholder="如：19:00、21:00"
                      value={timeWindows}
                      onChange={(e) => setTimeWindows(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">30天阶段目标 *</label>
                    <input
                      className="form-input"
                      placeholder="如：30天发布10条，跑出2条高潜内容"
                      value={goalTarget}
                      onChange={(e) => setGoalTarget(e.target.value)}
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label className="form-label">迭代规则</label>
                  <input
                    className="form-input"
                    placeholder="如：每周复盘1次，每次只改1-2个变量"
                    value={iterationRule}
                    onChange={(e) => setIterationRule(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">商业目标（可选）</label>
                  <input
                    className="form-input"
                    placeholder="如：私域引流、转化咨询、品牌曝光"
                    value={form.business_goal}
                    onChange={e => setForm(f => ({ ...f, business_goal: e.target.value }))}
                  />
                </div>
              </div>
            </section>

            <aside className="plan-final-side">
              <div className="plan-confirm-card">
                <div className="plan-confirm-title">生成前确认</div>
                <div className="plan-confirm-item"><span>账号/品牌：</span><strong>{form.client_name || '未填写'}</strong></div>
                <div className="plan-confirm-item"><span>行业：</span><strong>{form.industry || '未填写'}</strong></div>
                <div className="plan-confirm-item"><span>受众：</span><strong>{form.target_audience || '未填写'}</strong></div>
                <div className="plan-confirm-item"><span>发布节奏：</span><strong>{rhythmText}</strong></div>
                <div className="plan-confirm-item"><span>发布时间：</span><strong>{timeWindows || '未填写'}</strong></div>
                <div className="plan-confirm-item"><span>参考博主：</span><strong>{form.reference_blogger_ids.length} 位</strong></div>
                {selectedReferenceBloggers.length > 0 && (
                  <div className="plan-confirm-reference-list">
                    {selectedReferenceBloggers.map((blogger) => (
                      <span key={blogger.id} className="plan-reference-chip">
                        {blogger.nickname}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="plan-result-preview">
                <div className="plan-result-preview-title">这次会给你什么</div>
                <div className="plan-result-preview-list">
                  <div className="plan-result-preview-item">先创建项目草稿并保存问诊信息</div>
                  <div className="plan-result-preview-item">进入详情页后先生成账号定位方案</div>
                  <div className="plan-result-preview-item">确认定位后再生成 30 天日历</div>
                </div>
              </div>
              <div className="plan-confirm-note">
                创建完成后将进入详情页，按“定位 → 30天日历 → 单条脚本”分阶段落地。
              </div>
            </aside>
          </div>
        )}

        {mutation.isError && (
          <div className="error-tip">{(mutation.error as Error).message}</div>
        )}
        </div>

        <div className="modal-footer">
          {step > 1 && <button className="btn btn-ghost" onClick={() => setStep(s => Math.max(1, s - 1))}>上一步</button>}
          <button className="btn btn-ghost" onClick={onClose}>取消</button>
          {step < TOTAL_CREATE_STEPS ? (
            <button
              className="btn btn-primary"
              disabled={step === 1 && !canGoNextStep1}
              onClick={() => setStep((prev) => Math.min(TOTAL_CREATE_STEPS, prev + 1))}
            >
              {nextStepLabel} <ArrowRight size={14} />
            </button>
          ) : (
            <button
              className="btn btn-primary"
              disabled={!canSubmit || mutation.isPending}
              onClick={() => mutation.mutate(buildPayload())}
            >
              {mutation.isPending ?
                <><div className="spinner" style={{ width: 14, height: 14 }} /> 创建中...</> :
                <><Sparkles size={14} /> 创建项目并进入详情</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function PlanWorkspace() {
  const [showModal, setShowModal] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [jumpPageInput, setJumpPageInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | ProjectStage>('all');
  const [deleteConfirmId, setDeleteConfirmId] = useState<{ id: string, name: string } | null>(null);
  const [retryConfirmId, setRetryConfirmId] = useState<{ id: string, name: string } | null>(null);
  const [homepageEditId, setHomepageEditId] = useState<{ id: string, name: string } | null>(null);
  const [homepageUrl, setHomepageUrl] = useState('');
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: bloggers = [] } = useQuery({
    queryKey: ['bloggers'],
    queryFn: () => bloggerApi.list(),
  });
  const debouncedKeyword = useDebouncedValue(searchQuery.trim(), SEARCH_DEBOUNCE_MS);
  const selectedStatus = statusFilter === 'all' ? undefined : statusFilter;
  const hasActiveFilters = !!debouncedKeyword || statusFilter !== 'all';
  const bloggerNameMap = useMemo(
    () => new Map(bloggers.map((blogger) => [blogger.id, blogger.nickname])),
    [bloggers]
  );

  const { data: projectsPage, isLoading, isFetching } = useQuery({
    queryKey: ['planning-projects', page, pageSize, debouncedKeyword, selectedStatus],
    queryFn: () => planningApi.listPaged({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      keyword: debouncedKeyword || undefined,
      status: selectedStatus,
    }),
    refetchInterval: 8000,
  });
  const projects = projectsPage?.items ?? [];
  const totalProjects = projectsPage?.total ?? projects.length;
  const totalPages = Math.max(1, Math.ceil(totalProjects / pageSize));
  const hasPrevPage = page > 1;
  const hasNextPage = page < totalPages;

  const completedCount = projects.filter((p) => inferProjectStage(p) === 'completed').length;
  const generatingCount = projects.filter((p) => {
    const stage = inferProjectStage(p);
    return stage === 'strategy_generating' || stage === 'calendar_generating';
  }).length;
  const completionRate = projects.length > 0 ? Math.round((completedCount / projects.length) * 100) : 0;

  const deleteMutation = useMutation({
    mutationFn: planningApi.remove,
    onSuccess: () => {
      if (projects.length <= 1 && page > 1) {
        setPage((prev) => Math.max(1, prev - 1));
      }
      qc.invalidateQueries({ queryKey: ['planning-projects'] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: planningApi.retry,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['planning-projects'] }),
  });
  const generateStrategyMutation = useMutation({
    mutationFn: planningApi.generateStrategy,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['planning-projects'] }),
  });

  const homepageMutation = useMutation({
    mutationFn: ({ id, url }: { id: string; url: string }) => planningApi.updateHomepage(id, url),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['planning-projects'] });
      setHomepageEditId(null);
      setHomepageUrl('');
    },
  });

  const handleJumpPage = () => {
    const next = Number.parseInt(jumpPageInput, 10);
    if (!Number.isFinite(next)) return;
    const clamped = Math.min(totalPages, Math.max(1, next));
    setPage(clamped);
    setJumpPageInput('');
  };

  return (
    <div className="plan-page">
      <section className="plan-hero">
        <div>
          <div className="plan-hero-pill"><Sparkles size={13} /> Strategy Workspace</div>
          <h1>账号策划工作台</h1>
          <p>先生成账号定位方案，再基于定位生成 30 天日历，降低超时和整批返工。</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={16} /> 新建策划
        </button>
      </section>

      <section className="plan-workflow">
        <div className="plan-workflow-item">
          <span className="plan-workflow-index">1</span>
          <div>
            <div className="plan-workflow-title">定位输入</div>
            <div className="plan-workflow-desc">明确人群、差异点、内容支柱</div>
          </div>
        </div>
        <div className="plan-workflow-item">
          <span className="plan-workflow-index">2</span>
          <div>
            <div className="plan-workflow-title">对标拆解</div>
            <div className="plan-workflow-desc">选3-5个参考账号，抄流程不抄内容</div>
          </div>
        </div>
        <div className="plan-workflow-item">
          <span className="plan-workflow-index">3</span>
          <div>
            <div className="plan-workflow-title">定位生成</div>
            <div className="plan-workflow-desc">先产出定位、人设、内容支柱和表达策略</div>
          </div>
        </div>
        <div className="plan-workflow-item">
          <span className="plan-workflow-index">4</span>
          <div>
            <div className="plan-workflow-title">日历排布</div>
            <div className="plan-workflow-desc">确认定位后，再生成 30 天内容日历</div>
          </div>
        </div>
        <div className="plan-workflow-item">
          <span className="plan-workflow-index">5</span>
          <div>
            <div className="plan-workflow-title">脚本与迭代</div>
            <div className="plan-workflow-desc">脚本生成、回流复盘、每周只调1-2个变量</div>
          </div>
        </div>
      </section>

      {totalProjects > 0 && (
        <section className="plan-overview">
          <div className="plan-overview-card">
            <div className="plan-overview-label">项目总数</div>
            <div className="plan-overview-value">{totalProjects}</div>
          </div>
          <div className="plan-overview-card">
            <div className="plan-overview-label">当前页已完成</div>
            <div className="plan-overview-value">{completedCount}</div>
          </div>
          <div className="plan-overview-card">
            <div className="plan-overview-label">当前页生成中</div>
            <div className="plan-overview-value">{generatingCount}</div>
          </div>
          <div className="plan-overview-card">
            <div className="plan-overview-label">当前页完成率</div>
            <div className="plan-overview-value">{completionRate}%</div>
          </div>
        </section>
      )}

      <section className="plan-toolbar">
        <div className="plan-toolbar-search">
          <Search size={14} className="plan-toolbar-icon" />
          <input
            className="plan-search-input"
            placeholder="按客户名/行业/受众/账号昵称搜索..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
          />
          {searchQuery && (
            <button
              className="plan-search-clear"
              onClick={() => {
                setSearchQuery('');
                setPage(1);
              }}
            >
              <X size={12} />
            </button>
          )}
        </div>
        <div className="plan-toolbar-filter">
          <Filter size={13} style={{ color: 'var(--text-muted)' }} />
          <CustomSelect
            className="plan-filter-select"
            triggerClassName="plan-filter-select-trigger"
            value={statusFilter}
            options={STATUS_FILTER_OPTIONS}
            onChange={(value) => {
              setStatusFilter(value as 'all' | ProjectStage);
              setPage(1);
            }}
          />
        </div>
      </section>

      {isLoading ? (
        <div className="plan-loading">
          <div className="spinner" style={{ width: 32, height: 32 }} />
        </div>
      ) : totalProjects === 0 ? (
        <div className="card">
          <div className="empty-state">
            {hasActiveFilters ? (
              <>
                <div className="empty-icon"><Search size={24} /></div>
                <div className="empty-title">没有找到匹配项目</div>
                <div className="empty-desc">试试调整关键词或状态筛选条件</div>
              </>
            ) : (
              <>
                <div className="empty-icon"><Sparkles size={28} /></div>
                <div className="empty-title">还没有策划项目</div>
                <div className="empty-desc">先创建项目草稿，再分两步生成账号定位和 30 天内容日历。</div>
                <button className="btn btn-primary plan-empty-btn" onClick={() => setShowModal(true)}>
                  <Plus size={15} /> 创建第一个策划
                </button>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map(project => {
            const stage = inferProjectStage(project);
            const referenceNames = (project.reference_blogger_ids || [])
              .map((bloggerId) => bloggerNameMap.get(bloggerId))
              .filter((name): name is string => Boolean(name));
            const visibleReferenceNames = referenceNames.slice(0, 2);
            const extraReferenceCount = Math.max(referenceNames.length - visibleReferenceNames.length, 0);

            return (
            <div key={project.id} style={{ position: 'relative' }}>
              <div
                className="project-card card card-glow"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/planning/${project.id}`)}
              >
                {/* 卡片头部：和博主IP库一致的头像+信息布局 */}
                <div className="project-card-header">
                  <div className="project-card-avatar">
                    {project.account_avatar_url ? (
                      <img src={project.account_avatar_url} alt="" />
                    ) : (
                      <span>{(project.account_nickname || project.client_name)[0]}</span>
                    )}
                  </div>

                  <div className="project-card-info">
                    <div className="project-card-title-row">
                      <h3 className="project-card-name" title={project.account_nickname || project.client_name}>
                        {project.account_nickname || project.client_name}
                      </h3>
                    </div>
                    <div className="project-card-meta-row">
                      <span className="badge badge-purple project-card-industry-badge">{project.industry}</span>
                      <span className={`badge project-card-status-inline ${
                        stage === 'completed' ? 'badge-green' :
                        stage === 'strategy_completed' ? 'badge-blue' :
                        stage === 'draft' ? 'badge-purple' : 'badge-yellow'
                      }`}>
                        {stage === 'completed' ? <><CheckCircle size={10} /> 已完成</> :
                         stage === 'strategy_completed' ? '定位已完成' :
                         stage === 'strategy_generating' ? <><Clock size={10} /> 定位生成中...</> :
                         stage === 'calendar_generating' ? <><Clock size={10} /> 日历生成中...</> : '草稿'}
                      </span>
                    </div>
                    <div className="project-card-sig">
                      {project.account_signature || project.target_audience}
                    </div>
                    {referenceNames.length > 0 && (
                      <div className="project-card-reference-row">
                        <span className="project-card-reference-label">参考 IP</span>
                        <div className="project-card-reference-list">
                          {visibleReferenceNames.map((name) => (
                            <span key={name} className="project-card-reference-chip" title={name}>
                              {name}
                            </span>
                          ))}
                          {extraReferenceCount > 0 && (
                            <span className="project-card-reference-more">+{extraReferenceCount}</span>
                          )}
                        </div>
                      </div>
                    )}
                    {(project.account_follower_count != null || project.account_video_count != null) && (
                      <div className="project-card-stats">
                        {project.account_follower_count != null && (
                          <span>{project.account_follower_count >= 10000
                            ? `${(project.account_follower_count / 10000).toFixed(1)}w`
                            : project.account_follower_count} 粉丝</span>
                        )}
                        {project.account_video_count != null && (
                          <span>{project.account_video_count} 作品</span>
                        )}
                      </div>
                    )}
                    {project.account_nickname && (
                      <div className="project-card-client-row">
                        <span className="project-card-client-name">客户：{project.client_name}</span>
                        <button
                          className="btn btn-ghost project-card-client-refresh"
                          title="重新抓取账号数据"
                          onClick={e => {
                            e.preventDefault();
                            e.stopPropagation();
                            setHomepageEditId({ id: project.id, name: project.client_name });
                            setHomepageUrl(project.account_homepage_url || '');
                          }}
                        >
                          <RefreshCw size={10} />
                        </button>
                      </div>
                    )}
                    {!project.account_nickname && (
                      <button
                        className="btn btn-ghost project-card-homepage-btn"
                        onClick={e => {
                          e.preventDefault();
                          e.stopPropagation();
                          setHomepageEditId({ id: project.id, name: project.client_name });
                          setHomepageUrl('');
                        }}
                      >
                        <LinkIcon size={11} /> 补填账号主页
                      </button>
                    )}
                  </div>

                  {/* 右侧：状态 + 操作按钮 */}
                  <div className="project-card-actions">
                    {stage !== 'strategy_generating' && stage !== 'calendar_generating' && (
                      <button
                        className="btn btn-icon project-card-action-btn project-card-action-refresh"
                        title={project.account_plan ? '重新生成定位方案' : '生成定位方案'}
                        onClick={e => {
                          e.preventDefault();
                          e.stopPropagation();
                          if (project.account_plan) {
                            setRetryConfirmId({ id: project.id, name: project.client_name });
                          } else {
                            generateStrategyMutation.mutate(project.id, {
                              onError: (err) => notifyError('生成定位失败：' + err.message),
                            });
                          }
                        }}
                        disabled={generateStrategyMutation.isPending}
                      >
                        <RefreshCw size={14} />
                      </button>
                    )}
                    <button
                      className="btn btn-icon project-card-action-btn project-card-action-delete"
                      title={stage === 'strategy_generating' || stage === 'calendar_generating' ? '停止生成并删除' : '删除项目'}
                      onClick={e => {
                        e.preventDefault();
                        e.stopPropagation();
                        setDeleteConfirmId({ id: project.id, name: project.client_name });
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>

                {project.account_plan?.account_positioning?.core_identity && (
                  <div className="project-card-identity">
                    💡 {project.account_plan.account_positioning.core_identity}
                  </div>
                )}

                <div className="project-card-footer">
                  <span className="text-sm text-muted">
                    {formatBackendDate(project.created_at)}
                  </span>
                  <ArrowRight size={14} className="text-muted" />
                </div>
              </div>
            </div>
          )})}
        </div>
      )}

      {totalProjects > 0 && totalPages > 1 && (
        <section className="plan-pagination">
          <div className="plan-pagination-meta">
            第 {page} / {totalPages} 页 · 共 {totalProjects} 个项目
          </div>
          <div className="plan-pagination-actions">
            <CustomSelect
              className="plan-page-size"
              triggerClassName="form-input"
              value={String(pageSize)}
              options={PAGE_SIZE_OPTIONS.map((size) => ({
                value: String(size),
                label: `每页 ${size} 条`,
              }))}
              onChange={(value) => {
                setPageSize(Number(value));
                setPage(1);
              }}
            />
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
              className="form-input plan-page-jump"
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

      {showModal && <CreatePlanModal onClose={() => setShowModal(false)} />}

      {/* 重新生成确认弹窗 */}
      {retryConfirmId && (
        <div className="modal-overlay" onClick={() => !retryMutation.isPending && setRetryConfirmId(null)}>
          <div className="modal animate-scale-in" style={{ width: 400 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">重新生成定位方案</h2>
              <button 
                className="btn btn-icon btn-ghost" 
                onClick={() => setRetryConfirmId(null)}
                disabled={retryMutation.isPending}
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-4" style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              确定要重新生成项目 <strong>【{retryConfirmId.name}】</strong> 的账号定位方案吗？已有定位会被覆盖，后续 30 天日历需要基于新定位重新生成。
            </div>
            <div className="modal-footer" style={{ marginTop: 8 }}>
              <button 
                className="btn btn-ghost" 
                onClick={() => setRetryConfirmId(null)}
                disabled={retryMutation.isPending}
              >
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  retryMutation.mutate(retryConfirmId.id, {
                    onSuccess: () => setRetryConfirmId(null),
                    onError: (err) => notifyError('重新生成失败：' + err.message)
                  });
                }}
                disabled={retryMutation.isPending}
              >
                {retryMutation.isPending ? '生成中...' : '确认生成定位'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteConfirmId && (
        <div className="modal-overlay" onClick={() => !deleteMutation.isPending && setDeleteConfirmId(null)}>
          <div className="modal animate-scale-in" style={{ width: 400 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">确认删除</h2>
              <button
                className="btn btn-icon btn-ghost"
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleteMutation.isPending}
              >
                <X size={18} />
              </button>
            </div>
            <div className="p-4" style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              确定要删除项目 <strong>【{deleteConfirmId.name}】</strong> 吗？<br />
              <span className="text-muted" style={{ fontSize: 13, marginTop: 4, display: 'block' }}>
                如果该项目正在生成中，系统会自动中止生成任务。此操作不可恢复。
              </span>
            </div>
            <div className="modal-footer" style={{ marginTop: 8 }}>
              <button
                className="btn btn-ghost"
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleteMutation.isPending}
              >
                取消
              </button>
              <button
                className="btn btn-danger"
                onClick={() => {
                  deleteMutation.mutate(deleteConfirmId.id, {
                    onSuccess: () => setDeleteConfirmId(null),
                    onError: (err) => notifyError('删除项目失败：' + err.message)
                  });
                }}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 补填账号主页弹窗 */}
      {homepageEditId && (
        <div className="modal-overlay" onClick={() => !homepageMutation.isPending && setHomepageEditId(null)}>
          <div className="modal animate-scale-in" style={{ width: 460 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">补填账号主页</h2>
              <button className="btn btn-icon btn-ghost" onClick={() => setHomepageEditId(null)} disabled={homepageMutation.isPending}>
                <X size={18} />
              </button>
            </div>
            <div className="p-4 flex flex-col gap-3">
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                为项目 <strong>【{homepageEditId.name}】</strong> 填写策划账号的抖音主页地址，系统将自动抓取头像、昵称和简介。
              </div>
              <input
                className="form-input"
                placeholder="粘贴抖音主页链接，如 https://www.douyin.com/user/..."
                value={homepageUrl}
                onChange={e => setHomepageUrl(e.target.value)}
                autoFocus
              />
              {homepageMutation.isError && (
                <div className="error-tip">{(homepageMutation.error as Error).message}</div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setHomepageEditId(null)} disabled={homepageMutation.isPending}>取消</button>
              <button
                className="btn btn-primary"
                disabled={!homepageUrl.trim() || homepageMutation.isPending}
                onClick={() => homepageMutation.mutate({ id: homepageEditId.id, url: homepageUrl.trim() })}
              >
                {homepageMutation.isPending ? <><div className="spinner" style={{ width: 14, height: 14 }} /> 抓取中...</> : <><LinkIcon size={14} /> 确认抓取</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
