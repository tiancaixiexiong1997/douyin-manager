import { useEffect, useState, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useMutation, useQueryClient, useQueries } from '@tanstack/react-query';
import {
  bloggerApi,
  type Blogger,
  type AddBloggerRequest,
  type ReanalyzeBloggerRequest,
  type BloggerAnalysisReport,
  type BloggerProgress,
  type BloggerViralProfile,
  type PagedListResponse,
  type VideoAnalysis,
} from '../../api/client';
import { CustomSelect } from '../../components/CustomSelect';
import { Plus, X, Users, Trash2, RefreshCw, CheckCircle, Clock, Search, GitCompare, Filter, DouyinIcon, Sparkles } from '../../components/Icons';
import { formatBackendDate, formatBackendDateTime, toBackendTimestamp } from '../../utils/datetime';
import { notifyError, notifyInfo, notifySuccess } from '../../utils/notify';
import './BloggerLibrary.css';

const DEFAULT_PAGE_SIZE = 12;
const PAGE_SIZE_OPTIONS = [12, 24, 48];
const SEARCH_DEBOUNCE_MS = 350;
const PLATFORM_OPTIONS = ['douyin', 'tiktok', 'bilibili'] as const;
const PLATFORM_FILTER_OPTIONS = [
  { value: 'all', label: '全部平台' },
  ...PLATFORM_OPTIONS.map((platform) => ({ value: platform, label: platform })),
];
type AnalysisVideoSort = 'published_desc' | 'published_asc' | 'likes_desc' | 'likes_asc' | 'comments_desc' | 'comments_asc';

const ANALYSIS_VIDEO_SORT_OPTIONS: Array<{ value: AnalysisVideoSort; label: string }> = [
  { value: 'published_desc', label: '发布时间：最新优先' },
  { value: 'published_asc', label: '发布时间：最早优先' },
  { value: 'likes_desc', label: '点赞：高到低' },
  { value: 'likes_asc', label: '点赞：低到高' },
  { value: 'comments_desc', label: '评论：高到低' },
  { value: 'comments_asc', label: '评论：低到高' },
];
const TERMINAL_PROGRESS_STEPS = new Set(['idle', 'done', 'failed']);

function isActiveProgressStep(step?: string): boolean {
  return Boolean(step) && !TERMINAL_PROGRESS_STEPS.has(String(step));
}

function markBloggerAsAnalyzing(
  data: PagedListResponse<Blogger> | Blogger[] | undefined,
  bloggerId: string,
): PagedListResponse<Blogger> | Blogger[] | undefined {
  if (!data) return data;
  if (Array.isArray(data)) {
    return data.map((item) => (
      item.id === bloggerId
        ? { ...item, is_analyzed: false }
        : item
    ));
  }
  if (!Array.isArray(data.items)) return data;
  return {
    ...data,
    items: data.items.map((item) => (
      item.id === bloggerId
        ? { ...item, is_analyzed: false }
        : item
    )),
  };
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function normalizeTypicalHooks(report: BloggerAnalysisReport | undefined): string[] {
  const copywriting = report?.copywriting_dna;
  if (!copywriting) return [];
  const hooks = Array.isArray(copywriting.typical_hooks)
    ? copywriting.typical_hooks.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
  if (hooks.length > 0) return hooks;
  const fallback = String(copywriting.typical_hook || '').trim();
  return fallback ? [fallback] : [];
}

function normalizeTimelineEntries(profile: BloggerViralProfile | undefined) {
  if (!profile || !Array.isArray(profile.timeline_entries)) return [];
  return profile.timeline_entries.filter(
    (item) =>
      Boolean(
        item
        && (
          item.date
          || item.title
          || item.phase
          || item.performance_signal
          || item.topic_pattern
          || item.post_fire_role
          || item.why_it_mattered
        ),
      ),
  );
}

function getPublishedAtTimestamp(value?: string): number {
  return toBackendTimestamp(value);
}

function AddBloggerModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState<AddBloggerRequest>({
    url: '',
    representative_video_url: '',
    sample_count: 50,
    start_date: '',
    end_date: '',
    incremental_mode: false,
  });
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: bloggerApi.add,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['bloggers'] }); onClose(); },
    onError: (err: Error) => {
      notifyError(err.message || '博主采集失败，请稍后重试');
    },
  });

  const countOptions: { label: string; value: number | null }[] = [
    { label: '10条', value: 10 },
    { label: '50条', value: 50 },
    { label: '100条', value: 100 },
    { label: '全部', value: null },
  ];
  const hasDateRangeError = Boolean(form.start_date && form.end_date && form.end_date < form.start_date);
  const hasDateRange = Boolean(form.start_date || form.end_date);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">添加博主到 IP 库</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>

        <div className="flex flex-col gap-4">
          <div className="form-group">
            <label className="form-label">博主主页链接 *</label>
            <input
              className="form-input"
              placeholder="粘贴抖音或 TikTok 博主主页链接..."
              value={form.url}
              onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
            />
            <p className="form-hint">支持抖音主页链接，如：https://www.douyin.com/user/xxxxx</p>
          </div>

          <div className="form-group">
            <label className="form-label">采集视频数量</label>
            <div className="count-options">
              {countOptions.map(opt => (
                <button
                  key={String(opt.value)}
                  className={`count-option${form.sample_count === opt.value ? ' active' : ''}`}
                  onClick={() => setForm(f => ({ ...f, sample_count: opt.value }))}
                  type="button"
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="form-hint">
              {form.sample_count === null
                ? '将采集该博主所有作品标题数据（上限 5000 条），适合深度分析，耗时较长'
                : `采集最新 ${form.sample_count} 条视频的标题数据用于大盘分析`}
            </p>
          </div>

          <div className="form-group">
            <label className="form-label">采集模式</label>
            <button
              type="button"
              className={`mode-option ${form.incremental_mode ? 'mode-option-active' : ''}`}
              onClick={() => setForm((f) => ({ ...f, incremental_mode: !f.incremental_mode }))}
            >
              <div className="mode-option-title">{form.incremental_mode ? '增量采集（只拉新）' : '全量采集（默认）'}</div>
              <div className="mode-option-desc">
                {form.incremental_mode
                  ? '只采集尚未入库的新视频，降低重复计算成本。'
                  : '按数量或区间采集并参与完整分析。'}
              </div>
            </button>
          </div>

          <div className="form-group">
            <label className="form-label">代表作视频链接（选填）</label>
            <input
              className="form-input"
              placeholder="粘贴该博主最具代表性的单条视频链接..."
              value={form.representative_video_url || ''}
              onChange={e => setForm(f => ({ ...f, representative_video_url: e.target.value }))}
            />
            <p className="form-hint">如果有代表作，系统将下载该视频进行深度多模态分析（如拍摄手法等）；若不填则只做快速的大盘文字端画像分析。</p>
          </div>

          <div className="form-group">
            <label className="form-label">发布时间区间（选填）</label>
            <div className="date-range-grid">
              <input
                type="date"
                className="form-input"
                value={form.start_date || ''}
                max={form.end_date || undefined}
                onChange={e => setForm(f => ({ ...f, start_date: e.target.value || undefined }))}
              />
              <input
                type="date"
                className="form-input"
                value={form.end_date || ''}
                min={form.start_date || undefined}
                onChange={e => setForm(f => ({ ...f, end_date: e.target.value || undefined }))}
              />
            </div>
            <p className="form-hint">设置后将只采集该时间段内发布的视频（包含起止日期）。</p>
            {hasDateRange && (
              <p className="form-hint">已启用时间区间：将自动采集区间内全部视频，忽略“采集视频数量”。</p>
            )}
          </div>
        </div>

        {hasDateRangeError && (
          <div className="error-tip">结束日期不能早于开始日期</div>
        )}
        {mutation.isError && (
          <div className="error-tip">{(mutation.error as Error).message}</div>
        )}

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>取消</button>
          <button
            className="btn btn-primary"
            disabled={!form.url.trim() || mutation.isPending || hasDateRangeError}
            onClick={() => mutation.mutate({
              ...form,
              url: form.url.trim(),
              representative_video_url: form.representative_video_url?.trim() || undefined,
              sample_count: hasDateRange ? null : form.sample_count,
              start_date: form.start_date || undefined,
              end_date: form.end_date || undefined,
              incremental_mode: Boolean(form.incremental_mode),
            })}
          >
            {mutation.isPending ? <><div className="spinner" style={{ width: 14, height: 14 }} /> 添加中...</> : '开始采集分析'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ReanalyzeModal({
  blogger,
  onClose,
  onSubmit,
  isPending,
  errorMessage,
}: {
  blogger: Blogger;
  onClose: () => void;
  onSubmit: (payload: ReanalyzeBloggerRequest) => void;
  isPending: boolean;
  errorMessage?: string | null;
}) {
  const [form, setForm] = useState<ReanalyzeBloggerRequest>({
    sample_count: 100,
    start_date: '',
    end_date: '',
    incremental_mode: false,
  });
  const countOptions: { label: string; value: number | null }[] = [
    { label: '10条', value: 10 },
    { label: '50条', value: 50 },
    { label: '100条', value: 100 },
    { label: '全部', value: null },
  ];
  const hasDateRangeError = Boolean(form.start_date && form.end_date && form.end_date < form.start_date);
  const hasDateRange = Boolean(form.start_date || form.end_date);

  return (
    <div className="modal-overlay" onClick={() => !isPending && onClose()}>
      <div className="modal animate-scale-in reanalyze-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">重新采集设置</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose} disabled={isPending}><X size={18} /></button>
        </div>

        <div className="reanalyze-desc">
          将重新采集 <strong>{blogger.nickname}</strong> 的视频并刷新分析结果。
        </div>

        <div className="flex flex-col gap-4">
          <div className="form-group">
            <label className="form-label">采集视频数量</label>
            <div className="count-options">
              {countOptions.map(opt => (
                <button
                  key={String(opt.value)}
                  className={`count-option${form.sample_count === opt.value ? ' active' : ''}`}
                  onClick={() => setForm(f => ({ ...f, sample_count: opt.value }))}
                  type="button"
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <p className="form-hint">默认 100 条；选择“全部”将抓取该账号可获取的全部历史视频（上限 5000）。</p>
          </div>

          <div className="form-group">
            <label className="form-label">发布时间区间（选填）</label>
            <div className="date-range-grid">
              <input
                type="date"
                className="form-input"
                value={form.start_date || ''}
                max={form.end_date || undefined}
                onChange={e => setForm(f => ({ ...f, start_date: e.target.value || undefined }))}
              />
              <input
                type="date"
                className="form-input"
                value={form.end_date || ''}
                min={form.start_date || undefined}
                onChange={e => setForm(f => ({ ...f, end_date: e.target.value || undefined }))}
              />
            </div>
            <p className="form-hint">设置后仅重采集该时间段内发布的视频（包含起止日期）。</p>
            {hasDateRange && (
              <p className="form-hint">已启用时间区间：将自动采集区间内全部视频，忽略“采集视频数量”。</p>
            )}
          </div>

          <div className="form-group">
            <label className="form-label">重采集模式</label>
            <button
              type="button"
              className={`mode-option ${form.incremental_mode ? 'mode-option-active' : ''}`}
              onClick={() => setForm((f) => ({ ...f, incremental_mode: !f.incremental_mode }))}
            >
              <div className="mode-option-title">{form.incremental_mode ? '增量采集（推荐）' : '全量重采集'}</div>
              <div className="mode-option-desc">
                {form.incremental_mode
                  ? '只拉取新发布视频，不清空历史数据。'
                  : '重新覆盖采集历史视频并更新分析结果。'}
              </div>
            </button>
          </div>
        </div>

        {hasDateRangeError && (
          <div className="error-tip">结束日期不能早于开始日期</div>
        )}
        {errorMessage && (
          <div className="error-tip">{errorMessage}</div>
        )}

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={isPending}>取消</button>
          <button
            className="btn btn-primary"
            disabled={isPending || hasDateRangeError}
            onClick={() => onSubmit({
              sample_count: hasDateRange ? null : form.sample_count,
              start_date: form.start_date || undefined,
              end_date: form.end_date || undefined,
              incremental_mode: Boolean(form.incremental_mode),
            })}
          >
            {isPending ? <><div className="spinner" style={{ width: 14, height: 14 }} /> 提交中...</> : '开始重新采集'}
          </button>
        </div>
      </div>
    </div>
  );
}

function BloggerDetailModal({ blogger, onClose }: { blogger: Blogger; onClose: () => void }) {
  const qc = useQueryClient();
  const repTaskStorageKey = `blogger-rep-task-start:${blogger.id}`;
  const [repPendingVideoId, setRepPendingVideoId] = useState<string | null>(null);
  const [isTrackingRepTask, setIsTrackingRepTask] = useState(false);
  const [repTaskMessage, setRepTaskMessage] = useState('');
  const [repTaskElapsedSec, setRepTaskElapsedSec] = useState(0);
  const [repTaskStartedAtMs, setRepTaskStartedAtMs] = useState<number | null>(null);
  const [analysisVideoSort, setAnalysisVideoSort] = useState<AnalysisVideoSort>('published_desc');
  const { data: detail, isLoading: detailLoading, refetch: refetchDetail } = useQuery({
    queryKey: ['blogger-detail', blogger.id],
    queryFn: () => bloggerApi.get(blogger.id),
    enabled: true,
  });
  const { data: repTaskProgress } = useQuery({
    queryKey: ['blogger-representative-progress', blogger.id],
    queryFn: () => bloggerApi.getProgress(blogger.id),
    enabled: true,
    refetchInterval: 2500,
  });

  const report = detail?.analysis_report;
  const viralProfile = report?.viral_profile;
  const timelineEntries = normalizeTimelineEntries(viralProfile);
  const analysisVideos = useMemo(() => {
    const videos = detail?.videos?.filter((video) => !video.video_id.startsWith('rep_')) ?? [];
    const sortedVideos = [...videos];
    sortedVideos.sort((left, right) => {
      switch (analysisVideoSort) {
        case 'published_asc':
          return getPublishedAtTimestamp(left.published_at) - getPublishedAtTimestamp(right.published_at);
        case 'published_desc':
          return getPublishedAtTimestamp(right.published_at) - getPublishedAtTimestamp(left.published_at);
        case 'likes_asc':
          return left.like_count - right.like_count;
        case 'likes_desc':
          return right.like_count - left.like_count;
        case 'comments_asc':
          return left.comment_count - right.comment_count;
        case 'comments_desc':
          return right.comment_count - left.comment_count;
        default:
          return 0;
      }
    });
    return sortedVideos;
  }, [analysisVideoSort, detail?.videos]);
  const hasRepresentativeAnalysis = Boolean(
    detail?.videos?.some((video) => video.video_id.startsWith('rep_') && video.ai_analysis),
  );
  const viralProfileStep = repTaskProgress?.step;
  const isViralProfileBusy = viralProfileStep === 'viral_profile' || viralProfileStep === 'viral_profile_queued';
  const wasViralProfileBusyRef = useRef(false);
  const formatPublishDate = (value?: string) => {
    if (!value) return '发布未知';
    return `发布 ${formatBackendDateTime(value, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }, '发布未知')}`;
  };
  const formatElapsed = (seconds: number) => {
    if (seconds < 60) return `${seconds}秒`;
    const mins = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return rest > 0 ? `${mins}分${rest}秒` : `${mins}分钟`;
  };
  const formatTimelineDate = (value?: string) => {
    if (!value) return '日期未知';
    return formatBackendDate(value, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }, '日期未知');
  };

  const setRepMutation = useMutation({
    mutationFn: (video: import('../../api/client').BloggerVideo) =>
      bloggerApi.setRepresentative(blogger.id, {
        video_url: video.video_url!,
        video_id: video.video_id,
        title: video.title,
        cover_url: video.cover_url,
        like_count: video.like_count,
        published_at: video.published_at,
      }),
    onMutate: (video) => {
      setRepPendingVideoId(video.id);
      setRepTaskMessage('正在提交代表作解析任务...');
      if (!repTaskStartedAtMs) {
        const now = Date.now();
        setRepTaskStartedAtMs(now);
        localStorage.setItem(repTaskStorageKey, String(now));
      }
    },
    onSuccess: (res) => {
      notifyInfo(res.message || '已提交代表作解析任务');
      if (res.task_started === false) {
        setRepTaskMessage('');
        setIsTrackingRepTask(false);
        setRepPendingVideoId(null);
        setRepTaskElapsedSec(0);
        setRepTaskStartedAtMs(null);
        localStorage.removeItem(repTaskStorageKey);
        void refetchDetail();
        qc.invalidateQueries({ queryKey: ['bloggers'] });
        return;
      }
      if (res.task_enqueued === false) {
        setRepPendingVideoId(null);
      }
      if (!repTaskStartedAtMs) {
        const now = Date.now();
        setRepTaskStartedAtMs(now);
        localStorage.setItem(repTaskStorageKey, String(now));
      }
      setRepTaskMessage(res.message || '任务已提交，后台正在深度解析中...');
      setIsTrackingRepTask(true);
      setTimeout(() => refetchDetail(), 1200);
    },
    onError: (err: Error) => {
      setRepPendingVideoId(null);
      setIsTrackingRepTask(false);
      setRepTaskMessage('');
      setRepTaskElapsedSec(0);
      setRepTaskStartedAtMs(null);
      localStorage.removeItem(repTaskStorageKey);
      notifyError(err.message || '提交代表作解析失败，请稍后重试');
    },
  });

  const generateViralProfileMutation = useMutation({
    mutationFn: () => bloggerApi.generateViralProfile(blogger.id),
    onSuccess: (res) => {
      notifyInfo(res.message || '已提交爆款归因任务');
      qc.invalidateQueries({ queryKey: ['blogger-representative-progress', blogger.id] });
    },
    onError: (err: Error) => {
      notifyError(err.message || '生成爆款归因失败，请稍后重试');
    },
  });

  useEffect(() => {
    const tracking = setRepMutation.isPending || isTrackingRepTask || Boolean(repTaskStartedAtMs);
    if (!tracking || !repTaskStartedAtMs) {
      setRepTaskElapsedSec(0);
      return;
    }
    setRepTaskElapsedSec(Math.max(0, Math.floor((Date.now() - repTaskStartedAtMs) / 1000)));
    const timer = window.setInterval(() => {
      setRepTaskElapsedSec(Math.max(0, Math.floor((Date.now() - repTaskStartedAtMs) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isTrackingRepTask, repTaskStartedAtMs, setRepMutation.isPending]);

  useEffect(() => {
    const cached = localStorage.getItem(repTaskStorageKey);
    const parsed = cached ? Number(cached) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) {
      setRepTaskStartedAtMs(parsed);
    }
  }, [repTaskStorageKey]);

  useEffect(() => {
    if (!repTaskProgress) return;
    if (isViralProfileBusy) return;
    const step = repTaskProgress.step;
    const active = step !== 'idle' && step !== 'done' && step !== 'failed';
    if (active) {
      setIsTrackingRepTask(true);
      if (!repTaskStartedAtMs) {
        const cached = localStorage.getItem(repTaskStorageKey);
        const parsed = cached ? Number(cached) : NaN;
        if (Number.isFinite(parsed) && parsed > 0) {
          setRepTaskStartedAtMs(parsed);
        } else {
          const now = Date.now();
          setRepTaskStartedAtMs(now);
          localStorage.setItem(repTaskStorageKey, String(now));
        }
      }
      if (!setRepMutation.isPending) {
        setRepTaskMessage(repTaskProgress.message || '后台处理中...');
      }
      return;
    }
    if (step === 'idle' && !setRepMutation.isPending) {
      setIsTrackingRepTask(false);
      setRepTaskStartedAtMs(null);
      setRepTaskElapsedSec(0);
      localStorage.removeItem(repTaskStorageKey);
    }
  }, [isViralProfileBusy, repTaskProgress, repTaskStartedAtMs, repTaskStorageKey, setRepMutation.isPending]);

  useEffect(() => {
    if (!isTrackingRepTask || !repTaskProgress) return;
    if (isViralProfileBusy) return;
    setRepTaskMessage(repTaskProgress.message || '后台处理中...');

    if (repTaskProgress.step === 'done') {
      notifySuccess('代表作解析完成，报告已更新');
      setIsTrackingRepTask(false);
      setRepPendingVideoId(null);
      setRepTaskMessage('');
      setRepTaskElapsedSec(0);
      setRepTaskStartedAtMs(null);
      localStorage.removeItem(repTaskStorageKey);
      void refetchDetail();
      qc.invalidateQueries({ queryKey: ['bloggers'] });
      return;
    }

    if (repTaskProgress.step === 'failed') {
      notifyError('代表作解析失败，请稍后重试');
      setIsTrackingRepTask(false);
      setRepPendingVideoId(null);
      setRepTaskMessage('');
      setRepTaskElapsedSec(0);
      setRepTaskStartedAtMs(null);
      localStorage.removeItem(repTaskStorageKey);
      void refetchDetail();
    }
  }, [isTrackingRepTask, isViralProfileBusy, qc, refetchDetail, repTaskProgress, repTaskStorageKey]);

  useEffect(() => {
    if (!isTrackingRepTask || !repTaskProgress) return;
    if (isViralProfileBusy) return;
    if (repTaskProgress.step === 'done' || repTaskProgress.step === 'failed') return;
    void refetchDetail();
  }, [isTrackingRepTask, isViralProfileBusy, refetchDetail, repTaskProgress]);

  useEffect(() => {
    if (isViralProfileBusy) {
      wasViralProfileBusyRef.current = true;
      return;
    }
    if (!wasViralProfileBusyRef.current) return;
    wasViralProfileBusyRef.current = false;
    if (viralProfileStep === 'done') {
      notifySuccess('爆款归因报告生成完成');
    } else if (viralProfileStep === 'failed') {
      notifyError('爆款归因生成失败，请稍后重试');
    }
    void refetchDetail();
    qc.invalidateQueries({ queryKey: ['bloggers'] });
  }, [isViralProfileBusy, qc, refetchDetail, viralProfileStep]);

  const isRepProgressBusy = Boolean(
    repTaskProgress &&
      !isViralProfileBusy &&
      repTaskProgress.step !== 'idle' &&
      repTaskProgress.step !== 'done' &&
      repTaskProgress.step !== 'failed'
  );
  const isRepTaskBusy = setRepMutation.isPending || isTrackingRepTask || isRepProgressBusy;
  const resolveRepButtonText = (videoId: string) => {
    if (setRepMutation.isPending && repPendingVideoId === videoId) return '提交中...';
    if (isTrackingRepTask && repPendingVideoId === videoId) return '解析中...';
    if (isRepTaskBusy) return '处理中...';
    return '设为代表作';
  };

  const removeVideoMutation = useMutation({
    mutationFn: (videoId: string) => bloggerApi.removeVideo(blogger.id, videoId),
    onSuccess: () => {
      refetchDetail();
      // 如果删除了代表作，后端会触发重新生成报告，前端可以重新获取列表
      qc.invalidateQueries({ queryKey: ['bloggers'] });
    },
  });
  const [downloadingVideoId, setDownloadingVideoId] = useState<string | null>(null);
  const downloadMutation = useMutation({
    mutationFn: (params: { url: string; filename: string; video_id?: string }) =>
      bloggerApi.proxyDownload(params),
  });

  const buildSafeFilename = (rawName: string) => {
    const cleaned = rawName
      .replace(/[\\/:*?"<>|]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, 60);
    const base = cleaned || 'video';
    return base.toLowerCase().endsWith('.mp4') ? base : `${base}.mp4`;
  };

  const handleDownloadVideo = async (video: import('../../api/client').BloggerVideo) => {
    if (!video.video_url || downloadMutation.isPending) return;
    const filename = buildSafeFilename(video.title || video.video_id || 'video');
    setDownloadingVideoId(video.id);
    try {
      const blob = await downloadMutation.mutateAsync({
        url: video.video_url,
        filename,
        video_id: video.video_id,
      });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err: unknown) {
      notifyError(err instanceof Error ? err.message : '下载失败，请稍后重试');
    } finally {
      setDownloadingVideoId(null);
    }
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal blogger-detail-modal animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header blogger-detail-header">
          <div className="blogger-detail-head">
            <div className="blogger-detail-avatar">
              {blogger.avatar_url
                ? <img src={blogger.avatar_url} alt={blogger.nickname} />
                : <span>{blogger.nickname[0]}</span>}
              <div className={`platform-dot platform-${blogger.platform}`} />
            </div>
            <div className="blogger-detail-title-wrap">
              <h2 className="modal-title">{blogger.nickname}</h2>
              <div className="blogger-detail-subtitle">{blogger.signature || '暂无简介'}</div>
              <div className="blogger-detail-kpis">
                <span className="badge badge-blue">{(blogger.follower_count / 10000).toFixed(1)}w 粉丝</span>
                <span className="badge badge-purple">{blogger.video_count} 作品</span>
                {blogger.platform?.toLowerCase() === 'douyin' ? (
                  <span className="badge badge-green"><DouyinIcon size={13} style={{ marginRight: 4 }} />抖音</span>
                ) : (
                  <span className={`badge badge-green platform-label platform-${blogger.platform}`}>{blogger.platform}</span>
                )}
              </div>
            </div>
          </div>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="blogger-detail-body">
          {detailLoading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '32px 0', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
              <div className="spinner" style={{ width: 14, height: 14 }} />
              加载分析报告中...
            </div>
          ) : detail ? (
            <>
              {!report && (
                <div className="report-section">
                  <div className="empty-hint">综合报告暂未生成，代表作详情仍会在下方展示。</div>
                </div>
              )}
              <div className="report-section viral-profile-section">
                <div className="viral-profile-head">
                  <div>
                    <div className="report-section-title">爆款归因报告</div>
                    <div className="viral-profile-subtitle">解析这个账号是怎么策划的、为什么会火、哪些动作可复制。</div>
                  </div>
                  <button
                    className={`btn btn-primary btn-sm${isViralProfileBusy ? ' loading' : ''}`}
                    disabled={isViralProfileBusy || generateViralProfileMutation.isPending}
                    onClick={() => generateViralProfileMutation.mutate()}
                  >
                    {isViralProfileBusy || generateViralProfileMutation.isPending ? (
                      <><RefreshCw size={13} /> 生成中...</>
                    ) : (
                      <><Sparkles size={13} /> {viralProfile ? '重新生成' : '生成爆款归因'}</>
                    )}
                  </button>
                </div>
                {isViralProfileBusy && (
                  <div className="rep-task-status">
                    <RefreshCw size={12} className="rep-task-status-icon" />
                    <span>{repTaskProgress?.message || '爆款归因任务处理中...'}</span>
                  </div>
                )}
                {!viralProfile && !isViralProfileBusy && (
                  <div className="empty-hint">点击“生成爆款归因”，系统会输出策划逻辑、爆火原因与可复制动作清单。</div>
                )}
                {viralProfile && (
                  <div className="viral-profile-grid">
                    <div className="report-item">
                      <div className="report-item-label">策划逻辑</div>
                      <div className="report-item-value">{viralProfile.account_planning_logic || '数据不足'}</div>
                    </div>
                    <div className="report-item">
                      <div className="report-item-label">爆火原因</div>
                      <div className="report-item-value">{viralProfile.why_it_went_viral || '数据不足'}</div>
                    </div>
                    {typeof viralProfile.confidence_score === 'number' && (
                      <div className="viral-confidence">可信度：{viralProfile.confidence_score.toFixed(1)}/10</div>
                    )}
                    {viralProfile.content_playbook && viralProfile.content_playbook.length > 0 && (
                      <div className="viral-list-wrap">
                        <div className="report-item-label">可复制动作</div>
                        <ul className="report-elements">
                          {viralProfile.content_playbook.map((item, idx) => (
                            <li key={`${item}-${idx}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {viralProfile.risk_warnings && viralProfile.risk_warnings.length > 0 && (
                      <div className="viral-list-wrap">
                        <div className="report-item-label">不可盲抄项</div>
                        <ul className="report-elements">
                          {viralProfile.risk_warnings.map((item, idx) => (
                            <li key={`${item}-${idx}`}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {viralProfile.evidence_samples && viralProfile.evidence_samples.length > 0 && (
                      <div className="viral-list-wrap">
                        <div className="report-item-label">证据样本</div>
                        <div className="report-pillars">
                          {viralProfile.evidence_samples.map((sample, idx) => (
                            <span className="badge badge-blue" key={`${sample.title || 'sample'}-${idx}`}>
                              {sample.title || '样本'}：{sample.reason || '无说明'}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    {(viralProfile.timeline_overview || timelineEntries.length > 0 || viralProfile.post_fire_arrangement || (viralProfile.planning_takeaways && viralProfile.planning_takeaways.length > 0)) && (
                      <div className="viral-timeline-card">
                        <div className="report-item-label">起号日历回放</div>
                        {viralProfile.timeline_overview && (
                          <div className="viral-timeline-overview">{viralProfile.timeline_overview}</div>
                        )}
                        {timelineEntries.length > 0 && (
                          <div className="viral-timeline-list">
                            {timelineEntries.map((entry, idx) => (
                              <div key={`${entry.date || 'unknown'}-${entry.title || idx}`} className="viral-timeline-item">
                                <div className="viral-timeline-head">
                                  <div className="viral-timeline-date">{formatTimelineDate(entry.date)}</div>
                                  {entry.phase ? <span className="badge badge-blue">{entry.phase}</span> : null}
                                </div>
                                <div className="viral-timeline-title">{entry.title || '关键节点'}</div>
                                <div className="viral-timeline-meta">
                                  {entry.topic_pattern ? <span>选题模式：{entry.topic_pattern}</span> : null}
                                  {entry.post_fire_role ? <span>节点角色：{entry.post_fire_role}</span> : null}
                                  {entry.performance_signal ? <span>表现信号：{entry.performance_signal}</span> : null}
                                </div>
                                {entry.why_it_mattered ? <div className="viral-timeline-why">{entry.why_it_mattered}</div> : null}
                              </div>
                            ))}
                          </div>
                        )}
                        {viralProfile.post_fire_arrangement && (
                          <div className="viral-timeline-note">
                            <div className="report-item-label">爆点后内容安排</div>
                            <div className="report-item-value">{viralProfile.post_fire_arrangement}</div>
                          </div>
                        )}
                        {viralProfile.planning_takeaways && viralProfile.planning_takeaways.length > 0 && (
                          <div className="viral-timeline-note">
                            <div className="report-item-label">策划可借鉴点</div>
                            <ul className="report-elements">
                              {viralProfile.planning_takeaways.map((item, idx) => (
                                <li key={`${item}-${idx}`}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
              {report && (
                <>
                  {!hasRepresentativeAnalysis && (
                    <div className="report-callout">
                      当前未设置代表作，文案风格主要基于标题和描述样本推断，拍摄风格暂无法可靠判断。可在下方视频列表点击“设为代表作”，补充深度多模态分析来提升准确度。
                    </div>
                  )}
                  {report.ip_positioning && (
                    <div className="report-section">
                      <div className="report-section-title">IP 定位</div>
                      <div className="report-identity">{report.ip_positioning.core_identity}</div>
                      <div className="report-tags">
                        {report.ip_positioning.personality_tags?.map(tag => (
                          <span className="badge badge-purple" key={tag}>{tag}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {report.content_strategy && (
                    <div className="report-section">
                      <div className="report-section-title">内容策略</div>
                      <div className="report-grid">
                        <div className="report-item">
                          <div className="report-item-label">主要形式</div>
                          <div className="report-item-value">{report.content_strategy.dominant_content_type}</div>
                        </div>
                        <div className="report-item">
                          <div className="report-item-label">钩子模式</div>
                          <div className="report-item-value">{report.content_strategy.hook_patterns}</div>
                        </div>
                      </div>
                      {report.content_strategy.topic_pillars && (
                        <div className="report-pillars">
                          {report.content_strategy.topic_pillars.map(p => (
                            <span className="badge badge-blue" key={p}>{p}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {report.copywriting_dna && (
                    <div className="report-section">
                      <div className="report-section-title">文案风格</div>
                      {!hasRepresentativeAnalysis && (
                        <div className="report-inline-note">当前为标题/描述样本推断，不等同于完整口播文案分析。</div>
                      )}
                      {(() => {
                        const typicalHooks = normalizeTypicalHooks(report);
                        return (
                      <div className="report-grid">
                        <div className="report-item">
                          <div className="report-item-label">语言风格</div>
                          <div className="report-item-value">{report.copywriting_dna.tone_of_voice}</div>
                        </div>
                        <div className="report-item">
                          <div className="report-item-label">常用开头</div>
                          {typicalHooks.length > 0 ? (
                            <div className="report-pillars">
                              {typicalHooks.map((hook, idx) => (
                                <span className="badge badge-blue" key={`${hook}-${idx}`}>{hook}</span>
                              ))}
                            </div>
                          ) : (
                            <div className="report-item-value">数据不足</div>
                          )}
                        </div>
                      </div>
                        );
                      })()}
                    </div>
                  )}
                  {report.filming_signature && (
                    <div className="report-section">
                      <div className="report-section-title">拍摄风格</div>
                      {!hasRepresentativeAnalysis && (
                        <div className="report-inline-note">当前未设定代表作，这一栏默认只保留“数据不足，无法判断”。</div>
                      )}
                      <div className="report-grid">
                        <div className="report-item">
                          <div className="report-item-label">视觉风格</div>
                          <div className="report-item-value">{report.filming_signature.visual_style}</div>
                        </div>
                        <div className="report-item">
                          <div className="report-item-label">制作水准</div>
                          <div className="report-item-value">{report.filming_signature.production_level}</div>
                        </div>
                      </div>
                    </div>
                  )}
                  {report.reference_value && (
                    <div className="report-section">
                      <div className="report-section-title">参考价值</div>
                      <div className="report-score">参考评分：{report.reference_value.inspiration_score}/10</div>
                      <ul className="report-elements">
                        {report.reference_value.learnable_elements?.map((el, i) => (
                          <li key={i}>{el}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
              <div className="report-section">
                <div className="report-section-title">代表作深度解析（多模态）</div>
                {(() => {
                  const repVideos = detail.videos?.filter(v => v.video_id.startsWith('rep_')) ?? [];
                  if (!blogger.representative_video_url && repVideos.length === 0) {
                    return <div className="empty-hint">用户未添加博主代表作</div>;
                  }
                  if (repVideos.length === 0) {
                    return <div className="empty-hint">代表作分析中或解析异常...</div>;
                  }
                  return (
                    <div className="rep-list">
                      {repVideos.map((repVideo, idx) => {
                        const va = repVideo.ai_analysis as (VideoAnalysis & { error?: string; raw_analysis?: string }) | undefined;
                        return (
                          <div key={repVideo.id} className="rep-video-analysis">
                            {repVideos.length > 1 && (
                              <div className="rep-index-label">代表作 {idx + 1}</div>
                            )}
                            <div className="rep-video-meta">
                                {repVideo.cover_url && <img src={repVideo.cover_url} alt="cover" className="rep-cover" />}
                                <div className="rep-info">
                                  <div className="rep-title">{repVideo.title || '无标题'}</div>
                                  {va && <div className="rep-summary">{va.content_summary}</div>}
                                </div>
                                <button
                                  className="rep-delete-btn"
                                  onClick={() => removeVideoMutation.mutate(repVideo.id)}
                                  title="删除此代表作分析"
                                  disabled={removeVideoMutation.isPending}
                                >
                                  <X size={14} />
                                </button>
                              </div>
                            {va ? (
                              va.error ? (
                                <div className="error-tip" style={{ marginTop: 8 }}>
                                  解析失败: {va.error}
                                </div>
                              ) : va.raw_analysis ? (
                                <div className="error-tip" style={{ marginTop: 8 }}>
                                  AI 响应解析失败，原始内容已保存。请重新生成。
                                </div>
                              ) : (
                                <>
                                  <div className="rep-grid">
                                  <div className="rep-box">
                                    <div className="rep-box-label">拍摄手法</div>
                                    <div className="rep-box-content">
                                      <div><strong>镜头：</strong>{va.filming_style?.shot_types}</div>
                                      <div><strong>节奏：</strong>{va.filming_style?.editing_pace}</div>
                                      <div><strong>视觉：</strong>{va.filming_style?.visual_style}</div>
                                    </div>
                                  </div>
                                  <div className="rep-box">
                                    <div className="rep-box-label">文案结构</div>
                                    <div className="rep-box-content">
                                      <div><strong>钩子：</strong>{va.copywriting_style?.hook_method}</div>
                                      <div><strong>语调：</strong>{va.copywriting_style?.language_tone}</div>
                                      <div><strong>结构：</strong>{va.copywriting_style?.structure}</div>
                                    </div>
                                  </div>
                                  {va.audio_style && (
                                    <div className="rep-box rep-box-full">
                                      <div className="rep-box-label">音频风格</div>
                                      <div className="rep-box-content">
                                        <div><strong>BGM：</strong>{va.audio_style.bgm}</div>
                                        <div><strong>人声：</strong>{va.audio_style.voice_style}</div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                                  {va.viral_factors && (
                                    <div className="rep-viral">
                                      <strong>爆款基因：</strong> {va.viral_factors.join(' · ')}
                                    </div>
                                  )}
                                </>
                              )
                            ) : (
                              <div className="empty-hint" style={{ marginTop: 8 }}>该代表作 AI 分析中...</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
              {analysisVideos.length > 0 && (
                <div className="report-section">
                  <div className="analysis-video-head">
                    <div className="report-section-title">
                      参与分析的视频（{analysisVideos.length} 条）
                    </div>
                    <div className="analysis-video-sort">
                      <span className="analysis-video-sort-label">排序</span>
                      <CustomSelect
                        className="analysis-video-sort-select"
                        triggerClassName="analysis-video-sort-trigger"
                        value={analysisVideoSort}
                        options={ANALYSIS_VIDEO_SORT_OPTIONS}
                        onChange={(value) => setAnalysisVideoSort(value as AnalysisVideoSort)}
                      />
                    </div>
                  </div>
                  {isRepTaskBusy && (
                    <div className="rep-task-status">
                      <RefreshCw size={12} className="rep-task-status-icon" />
                      <span>
                        {repTaskMessage || repTaskProgress?.message || '代表作任务处理中...'}
                        {repTaskElapsedSec > 0 ? `（已耗时 ${formatElapsed(repTaskElapsedSec)}）` : ''}
                      </span>
                    </div>
                  )}
                  <div className="video-list">
                    {analysisVideos.map(video => (
                      <div key={video.id} className="video-item">
                        {video.cover_url && (
                          <img className="video-cover" src={video.cover_url} alt={video.title || ''} />
                        )}
                        <div className="video-info">
                          <div className="video-title">{video.title || '（无标题）'}</div>
                          <div className="video-stats">
                            <span>点赞 {video.like_count.toLocaleString()}</span>
                            <span>评论 {video.comment_count.toLocaleString()}</span>
                            <span>时长 {video.duration}s</span>
                            <span>{formatPublishDate(video.published_at)}</span>
                          </div>
                          <div className="video-actions">
                            <a
                              className="video-link"
                              href={`https://www.douyin.com/video/${video.video_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              在抖音查看 →
                            </a>
                            {video.video_url && (
                              <button
                                className="video-download"
                                type="button"
                                onClick={() => void handleDownloadVideo(video)}
                                disabled={downloadMutation.isPending}
                                aria-busy={downloadingVideoId === video.id && downloadMutation.isPending}
                              >
                                {downloadingVideoId === video.id && downloadMutation.isPending ? '下载中...' : '⬇ 无水印下载'}
                              </button>
                            )}
                            {video.video_url && !video.video_id.startsWith('rep_') && (
                              <button
                                className={`set-rep-btn${isRepTaskBusy ? ' loading' : ''}${repPendingVideoId === video.id ? ' active' : ''}`}
                                disabled={isRepTaskBusy}
                                onClick={() => setRepMutation.mutate(video)}
                                title="将此视频设为代表作并触发 AI 深度多模态析帧"
                              >
                                {resolveRepButtonText(video.id)}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: 13 }}>
              暂无博主详情数据
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

function BloggerCard({ blogger, onDelete, onReanalyze, selected, onSelect }: {
  blogger: Blogger;
  onDelete: (id: string) => void;
  onReanalyze: (id: string) => void;
  selected?: boolean;
  onSelect?: (id: string, checked: boolean) => void;
}) {
  const [showDetail, setShowDetail] = useState(false);
  const qc = useQueryClient();
  const cachedProgress = qc.getQueryData<BloggerProgress>(['blogger-progress', blogger.id]);
  const shouldTrackProgress = !blogger.is_analyzed || isActiveProgressStep(cachedProgress?.step);

  // NOTE: 未完成分析或刚触发重采集时轮询进度（每 3 秒），终态后自动停止。
  const { data: progress } = useQuery({
    queryKey: ['blogger-progress', blogger.id],
    queryFn: () => bloggerApi.getProgress(blogger.id),
    enabled: shouldTrackProgress,
    refetchInterval: (query) => {
      const step = (query.state.data as BloggerProgress | undefined)?.step ?? cachedProgress?.step;
      if (isActiveProgressStep(step)) return 3000;
      return !blogger.is_analyzed ? 3000 : false;
    },
  });
  const shouldShowProgress = Boolean(progress && progress.step !== 'done' && progress.step !== 'idle');

  // 进度步骤文字颜色映射
  const progressColorMap: Record<string, string> = {
    queued: '#64748b',
    processing: '#3b82f6',
    crawling: '#f59e0b',
    saving: '#f59e0b',
    downloading: '#3b82f6',
    compressing: '#3b82f6',
    ai_video: '#8b5cf6',
    refresh_queued: '#64748b',
    ai_report: '#8b5cf6',
    done: '#22c55e',
    failed: '#ef4444',
  };
  const progressColor = progress ? (progressColorMap[progress.step] || 'var(--text-muted)') : undefined;
  const isProgressFailed = progress?.step === 'failed';
  const isProgressDone = progress?.step === 'done';
  const progressMessage = progress?.message || '任务执行中...';
  const progressIcon = isProgressFailed ? (
    <X size={10} style={{ marginRight: 3 }} />
  ) : isProgressDone ? (
    <CheckCircle size={10} style={{ marginRight: 3 }} />
  ) : (
    <Clock size={10} style={{ marginRight: 3, animation: 'spin 1.5s linear infinite' }} />
  );

  return (
    <div className={`blogger-card card card-glow animate-fade-in${selected ? ' blogger-card-selected' : ''}`}>
      <div className="blogger-card-header">
        {/* 对比勾选框 */}
        {onSelect && (
          <label className="compare-checkbox">
            <input
              type="checkbox"
              checked={!!selected}
              onChange={e => onSelect(blogger.id, e.target.checked)}
            />
          </label>
        )}
        <div className="blogger-card-avatar">
          {blogger.avatar_url ? (
            <img src={blogger.avatar_url} alt={blogger.nickname} />
          ) : (
            <span>{blogger.nickname[0]}</span>
          )}
          <div className={`platform-dot platform-${blogger.platform}`} />
        </div>

        <div className="blogger-card-info">
          <div className="flex items-center gap-2">
            <h3 className="blogger-card-name">{blogger.nickname}</h3>
            {shouldShowProgress ? (
              <span
                className="badge badge-progress"
                style={{ fontSize: 11, color: progressColor, background: `${progressColor}18`, borderColor: `${progressColor}40` }}
                title={progressMessage}
              >
                {progressIcon}
                {progressMessage}
              </span>
            ) : blogger.is_analyzed ? (
              <span className="badge badge-green" style={{ fontSize: 11 }}>
                <CheckCircle size={10} style={{ marginRight: 3 }} />已分析
              </span>
            ) : (
              <span className="badge badge-yellow" style={{ fontSize: 11 }}>
                <Clock size={10} style={{ marginRight: 3 }} />分析中
              </span>
            )}
          </div>
          <div className="blogger-card-sig">{blogger.signature || '暂无简介'}</div>
          <div className="blogger-card-stats">
            <span>{(blogger.follower_count / 10000).toFixed(1)}w 粉丝</span>
            <span>·</span>
            <span>{blogger.video_count} 作品</span>
            <span>·</span>
            {blogger.platform?.toLowerCase() === 'douyin' ? (
              <DouyinIcon size={14} style={{ color: 'var(--text-primary)' }} />
            ) : (
              <span className={`platform-label platform-${blogger.platform}`}>{blogger.platform}</span>
            )}
          </div>
        </div>

        <div className="blogger-card-actions">
          <button className="btn btn-icon btn-ghost" title="重新采集更新数据" onClick={() => onReanalyze(blogger.id)}>
            <RefreshCw size={14} />
          </button>
          <button className="btn btn-icon btn-danger" title="删除" onClick={() => onDelete(blogger.id)}>
            <Trash2 size={14} />
          </button>
          {blogger.is_analyzed && (
            <button className="btn btn-ghost blogger-detail-btn" onClick={() => setShowDetail(true)}>
              查看详情
            </button>
          )}
        </div>
      </div>

      {showDetail && <BloggerDetailModal blogger={blogger} onClose={() => setShowDetail(false)} />}
    </div>
  );
}


// ===== 博主对比视图模态框 =====
function CompareModal({ selectedIds, bloggers, onClose }: {
  selectedIds: string[];
  bloggers: Blogger[];
  onClose: () => void;
}) {
  const selected = bloggers.filter(b => selectedIds.includes(b.id));
  const queries = useQueries({
    queries: selected.map((b) => ({
      queryKey: ['blogger-detail', b.id],
      queryFn: () => bloggerApi.get(b.id),
      enabled: b.is_analyzed,
    })),
  });

  const fields: Array<{ label: string; get: (r?: BloggerAnalysisReport) => string | undefined }> = [
    { label: '核心人设', get: (r) => r?.ip_positioning?.core_identity },
    { label: '受众群体', get: (r) => r?.ip_positioning?.target_audience },
    { label: '人设标签', get: (r) => r?.ip_positioning?.personality_tags?.join(' · ') },
    { label: '主要内容类型', get: (r) => r?.content_strategy?.dominant_content_type },
    { label: '钩子模式', get: (r) => r?.content_strategy?.hook_patterns },
    { label: '视觉风格', get: (r) => r?.filming_signature?.visual_style },
    { label: '文案语调', get: (r) => r?.copywriting_dna?.tone_of_voice },
    { label: '成功公式', get: (r) => r?.growth_insights?.success_formula },
    {
      label: '参考评分',
      get: (r) => (r?.reference_value?.inspiration_score != null ? `${r.reference_value.inspiration_score}/10` : undefined),
    },
  ];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal compare-modal animate-scale-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">🔬 博主横向对比（{selected.length} 位）</h2>
          <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="compare-table-wrap">
          <table className="compare-table">
            <thead>
              <tr>
                <th className="compare-field-col">维度</th>
                {selected.map(b => (
                  <th key={b.id} className="compare-blogger-col">
                    <div className="compare-avatar">
                      {b.avatar_url ? <img src={b.avatar_url} alt={b.nickname} /> : <span>{b.nickname[0]}</span>}
                    </div>
                    <div>{b.nickname}</div>
                    <div className="compare-stat">{(b.follower_count / 10000).toFixed(1)}w 粉</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fields.map(field => (
                <tr key={field.label}>
                  <td className="compare-label">{field.label}</td>
                  {queries.map((q, i) => (
                    <td key={i} className="compare-cell">
                      {q.isLoading ? <div className="spinner" style={{ width: 12, height: 12 }} /> :
                       !selected[i].is_analyzed ? <span className="compare-pending">分析中...</span> :
                       field.get(q.data?.analysis_report) || <span className="compare-empty">—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function BloggerLibrary() {
  const [showModal, setShowModal] = useState(false);
  const [reanalyzeTarget, setReanalyzeTarget] = useState<Blogger | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [jumpPageInput, setJumpPageInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [platformFilter, setPlatformFilter] = useState('all');
  const [compareMode, setCompareMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showCompare, setShowCompare] = useState(false);
  const qc = useQueryClient();
  const debouncedKeyword = useDebouncedValue(searchQuery.trim(), SEARCH_DEBOUNCE_MS);
  const selectedPlatform = platformFilter === 'all' ? undefined : platformFilter;

  const { data: bloggerPage, isLoading, isFetching } = useQuery({
    queryKey: ['bloggers', page, pageSize, debouncedKeyword, selectedPlatform],
    queryFn: () => bloggerApi.listPaged({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      keyword: debouncedKeyword || undefined,
      platform: selectedPlatform,
    }),
    refetchInterval: (query) => {
      const data = query.state.data as { items?: Blogger[] } | undefined;
      const hasAnalyzing = data?.items?.some((b: Blogger) => !b.is_analyzed);
      return hasAnalyzing ? 5000 : false;
    },
  });
  const bloggers = useMemo(() => bloggerPage?.items ?? [], [bloggerPage?.items]);
  const totalBloggers = bloggerPage?.total ?? bloggers.length;
  const totalPages = Math.max(1, Math.ceil(totalBloggers / pageSize));
  const hasPrevPage = page > 1;
  const hasNextPage = page < totalPages;
  const analyzedCount = bloggers.filter((b) => b.is_analyzed).length;
  const analyzingCount = bloggers.length - analyzedCount;
  const coverage = bloggers.length > 0 ? Math.round((analyzedCount / bloggers.length) * 100) : 0;

  const deleteMutation = useMutation({
    mutationFn: bloggerApi.remove,
    onSuccess: () => {
      if (bloggers.length <= 1 && page > 1) {
        setPage((prev) => Math.max(1, prev - 1));
      }
      qc.invalidateQueries({ queryKey: ['bloggers'] });
      setDeleteConfirmId(null);
    },
  });

  const reanalyzeMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ReanalyzeBloggerRequest }) => bloggerApi.reanalyze(id, data),
    onSuccess: (_result, variables) => {
      qc.setQueryData<BloggerProgress>(['blogger-progress', variables.id], {
        step: 'queued',
        message: '重采集任务已提交',
      });
      qc.setQueriesData(
        { queryKey: ['bloggers'] },
        (oldData: PagedListResponse<Blogger> | Blogger[] | undefined) => markBloggerAsAnalyzing(oldData, variables.id),
      );
      qc.invalidateQueries({ queryKey: ['bloggers'] });
      qc.invalidateQueries({ queryKey: ['blogger-progress', variables.id] });
      qc.invalidateQueries({ queryKey: ['blogger-detail', variables.id] });
      setReanalyzeTarget(null);
    },
  });

  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleSelect = (id: string, checked: boolean) => {
    setSelectedIds(prev => checked ? [...prev, id] : prev.filter(x => x !== id));
  };

  const handleJumpPage = () => {
    const next = Number.parseInt(jumpPageInput, 10);
    if (!Number.isFinite(next)) return;
    const clamped = Math.min(totalPages, Math.max(1, next));
    setPage(clamped);
    setSelectedIds([]);
    setShowCompare(false);
    setJumpPageInput('');
  };

  return (
    <div className="blogger-page">
      <section className="blogger-hero">
        <div className="blogger-hero-head">
          <div className="blogger-hero-pill">
            <Users size={14} />
            博主资产管理
          </div>
          <h1>博主 IP 库</h1>
          <p>统一管理对标账号，追踪 AI 分析进度，快速进入深度对比和复用。</p>
        </div>

        <div className="blogger-hero-actions">
          <div className="flex items-center gap-2">
            <button
              className={`btn ${compareMode ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => { setCompareMode(!compareMode); if (compareMode) setSelectedIds([]); }}
            >
              <GitCompare size={15} /> {compareMode ? `对比模式（已选 ${selectedIds.length}）` : '对比博主'}
            </button>
            {compareMode && selectedIds.length >= 2 && (
              <button className="btn btn-primary" onClick={() => setShowCompare(true)}>
                查看对比
              </button>
            )}
            <button className="btn btn-primary" onClick={() => setShowModal(true)}>
              <Plus size={16} /> 添加博主
            </button>
          </div>
        </div>
      </section>

      {totalBloggers > 0 && (
        <section className="blogger-overview">
          <div className="blogger-overview-card">
            <div className="blogger-overview-label">总博主数</div>
            <div className="blogger-overview-value">{totalBloggers}</div>
          </div>
          <div className="blogger-overview-card">
            <div className="blogger-overview-label">当前页已分析</div>
            <div className="blogger-overview-value">{analyzedCount}</div>
          </div>
          <div className="blogger-overview-card">
            <div className="blogger-overview-label">当前页分析中</div>
            <div className="blogger-overview-value">{analyzingCount}</div>
          </div>
          <div className="blogger-overview-card">
            <div className="blogger-overview-label">当前页覆盖率</div>
            <div className="blogger-overview-value">{coverage}%</div>
          </div>
        </section>
      )}

      {totalBloggers > 0 && (
        <section className="blogger-toolbar-wrap">
          <div className="toolbar">
            <div className="search-wrap">
              <Search size={14} className="search-icon" />
              <input
                className="search-input"
                placeholder="按昵称/简介/平台ID搜索..."
                value={searchQuery}
                onChange={e => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                  setSelectedIds([]);
                  setShowCompare(false);
                }}
              />
              {searchQuery && (
                <button
                  className="search-clear"
                  onClick={() => {
                    setSearchQuery('');
                    setPage(1);
                    setSelectedIds([]);
                    setShowCompare(false);
                  }}
                >
                  <X size={12} />
                </button>
              )}
            </div>
            <div className="filter-wrap">
              <Filter size={13} style={{ color: 'var(--text-muted)' }} />
              <CustomSelect
                className="filter-select"
                triggerClassName="filter-select-trigger"
                value={platformFilter}
                options={PLATFORM_FILTER_OPTIONS}
                onChange={value => {
                  setPlatformFilter(value);
                  setPage(1);
                  setSelectedIds([]);
                  setShowCompare(false);
                }}
              />
            </div>
          </div>
        </section>
      )}

      {isLoading ? (
        <div className="blogger-loading">
          <div className="spinner" style={{ width: 32, height: 32 }} />
        </div>
      ) : totalBloggers === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon"><Users size={28} /></div>
            <div className="empty-title">IP 库里还没有博主</div>
            <div className="empty-desc">
              添加你想研究的对标博主，AI 会自动分析他们的拍摄风格、文案特点和内容策略
            </div>
            <button className="btn btn-primary blogger-empty-btn" onClick={() => setShowModal(true)}>
              <Plus size={15} /> 添加第一个博主
            </button>
          </div>
        </div>
      ) : bloggers.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon"><Search size={24} /></div>
            <div className="empty-title">没有找到匹配的博主</div>
            <div className="empty-desc">试试调整关键词或平台筛选条件</div>
          </div>
        </div>
      ) : (
        <div className="blogger-grid">
          {bloggers.map(blogger => (
            <BloggerCard
              key={blogger.id}
              blogger={blogger}
              onDelete={(id) => setDeleteConfirmId(id)}
              onReanalyze={(id) => {
                const target = bloggers.find((item) => item.id === id);
                if (!target) return;
                reanalyzeMutation.reset();
                setReanalyzeTarget(target);
              }}
              selected={compareMode ? selectedIds.includes(blogger.id) : undefined}
              onSelect={compareMode ? handleSelect : undefined}
            />
          ))}
        </div>
      )}

      {totalBloggers > 0 && totalPages > 1 && (
        <section className="blogger-pagination">
          <div className="blogger-pagination-meta">
            第 {page} / {totalPages} 页 · 共 {totalBloggers} 位博主
          </div>
          <div className="blogger-pagination-actions">
            <CustomSelect
              className="blogger-page-size"
              triggerClassName="form-input"
              value={String(pageSize)}
              options={PAGE_SIZE_OPTIONS.map((size) => ({
                value: String(size),
                label: `每页 ${size} 条`,
              }))}
              onChange={(value) => {
                setPageSize(Number(value));
                setPage(1);
                setSelectedIds([]);
                setShowCompare(false);
              }}
            />
            <button
              className="btn btn-ghost btn-sm"
              disabled={!hasPrevPage || isFetching}
              onClick={() => {
                setPage((prev) => Math.max(1, prev - 1));
                setSelectedIds([]);
                setShowCompare(false);
              }}
            >
              上一页
            </button>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!hasNextPage || isFetching}
              onClick={() => {
                setPage((prev) => Math.min(totalPages, prev + 1));
                setSelectedIds([]);
                setShowCompare(false);
              }}
            >
              下一页
            </button>
            <input
              className="form-input blogger-page-jump"
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

      {showModal && <AddBloggerModal onClose={() => setShowModal(false)} />}
      {reanalyzeTarget && (
        <ReanalyzeModal
          blogger={reanalyzeTarget}
          onClose={() => {
            if (reanalyzeMutation.isPending) return;
            reanalyzeMutation.reset();
            setReanalyzeTarget(null);
          }}
          onSubmit={(data) => reanalyzeMutation.mutate({ id: reanalyzeTarget.id, data })}
          isPending={reanalyzeMutation.isPending}
          errorMessage={reanalyzeMutation.isError ? (reanalyzeMutation.error as Error).message : null}
        />
      )}
      {showCompare && (
        <CompareModal
          selectedIds={selectedIds}
          bloggers={bloggers}
          onClose={() => setShowCompare(false)}
        />
      )}

      {/* 删除确认弹窗 */}
      {deleteConfirmId && (
        <div className="modal-overlay" onClick={() => !deleteMutation.isPending && setDeleteConfirmId(null)}>
          <div className="modal animate-scale-in blogger-delete-modal" onClick={e => e.stopPropagation()}>
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
            <div className="blogger-delete-desc">
              您确定要将该博主移出 IP 库吗？删除后相关的数据分析也将被清除，该操作不可恢复。
            </div>
            <div className="modal-footer blogger-delete-footer">
              <button 
                className="btn btn-ghost" 
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleteMutation.isPending}
              >
                取消
              </button>
              <button
                className="btn btn-danger"
                onClick={() => deleteMutation.mutate(deleteConfirmId)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
