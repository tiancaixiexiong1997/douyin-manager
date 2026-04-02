import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toPng } from 'html-to-image';
import { scriptApi, planningApi } from '../../api/client';
import type { ExtractionCreateRequest, ExtractionListResponse, ExtractionResponse, ExtractionStatus } from '../../api/client';
import { Sparkles, RefreshCw } from '../../components/Icons';
import { AlertCircle, Trash2, ExternalLink, ChevronDown, Link2, Users, FileEdit, Clock, PlayCircle, Wand2, Save, X, Download, Pencil } from 'lucide-react';
import { notifyError, notifyInfo, notifySuccess } from '../../utils/notify';
import './ScriptExtraction.css';

// 提取文本中的真正的 URL，防爬短链可能夹带大段宣传语
const extractUrl = (text: string) => {
  const match = text.match(/(https?:\/\/[^\s]+)/);
  return match ? match[1] : text;
};

const sanitizeFilename = (value: string) => value
  .replace(/[\\/:*?"<>|]+/g, '-')
  .replace(/\s+/g, '-')
  .replace(/-+/g, '-')
  .replace(/^-|-$/g, '')
  .slice(0, 80) || 'script-analysis';

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const TRANSIENT_FAILURE_PATTERN = /timeout|timed out|超时|网络|network|连接|connection|502|503|504|429|繁忙|网关|rate limit/i;

function SmileEye({
  mouseX,
  mouseY,
  maxDistance = 6,
  isBlinking = false,
}: {
  mouseX: number;
  mouseY: number;
  maxDistance?: number;
  isBlinking?: boolean;
}) {
  const cx = window.innerWidth / 2;
  const cy = window.innerHeight / 2;
  const dx = mouseX - cx;
  const dy = mouseY - cy;
  const distance = Math.min(Math.hypot(dx, dy), maxDistance);
  const angle = Math.atan2(dy, dx);
  const x = Math.cos(angle) * distance;
  const y = Math.sin(angle) * distance;

  return (
    <div className="smile-eye" style={{ height: isBlinking ? 3 : 26 }}>
      {!isBlinking && <div className="smile-pupil" style={{ transform: `translate(${x}px, ${y}px)` }} />}
    </div>
  );
}

function WaitingSmileFace() {
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  const [isBlinking, setIsBlinking] = useState(false);

  useEffect(() => {
    const onMove = (e: MouseEvent) => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener('mousemove', onMove);
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    let blinkTimer: number;
    let closeTimer: number;
    const scheduleBlink = () => {
      blinkTimer = window.setTimeout(() => {
        setIsBlinking(true);
        closeTimer = window.setTimeout(() => setIsBlinking(false), 140);
        scheduleBlink();
      }, Math.random() * 3200 + 2200);
    };
    scheduleBlink();
    return () => {
      window.clearTimeout(blinkTimer);
      window.clearTimeout(closeTimer);
    };
  }, []);

  return (
    <div className="waiting-smile-face" aria-hidden="true">
      <div className="waiting-smile-eyes">
        <SmileEye mouseX={mouse.x} mouseY={mouse.y} isBlinking={isBlinking} />
        <SmileEye mouseX={mouse.x} mouseY={mouse.y} isBlinking={isBlinking} />
      </div>
      <div className="waiting-smile-mouth" />
      <div className="waiting-smile-cheek waiting-smile-cheek-left" />
      <div className="waiting-smile-cheek waiting-smile-cheek-right" />
    </div>
  );
}

export default function ScriptExtraction() {
  const [videoUrl, setVideoUrl] = useState('');
  const [userPrompt, setUserPrompt] = useState('');
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [activeExtId, setActiveExtId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isEditingAnalysis, setIsEditingAnalysis] = useState(false);
  const [editedAnalysisTitle, setEditedAnalysisTitle] = useState('');
  const [editedHighlightAnalysis, setEditedHighlightAnalysis] = useState<ExtractionResponse['highlight_analysis'] | null>(null);
  const [isEditingGeneratedScript, setIsEditingGeneratedScript] = useState(false);
  const [editedGeneratedScript, setEditedGeneratedScript] = useState<ExtractionResponse['generated_script'] | null>(null);
  const [isExportingAnalysis, setIsExportingAnalysis] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const analysisExportRef = useRef<HTMLDivElement | null>(null);
  const autoRetriedExtractionIdsRef = useRef<Set<string>>(new Set());
  const isDraftHydratedRef = useRef(false);
  const isDraftDirtyRef = useRef(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const queryClient = useQueryClient();
  const markDraftDirty = useCallback(() => {
    isDraftDirtyRef.current = true;
    isDraftHydratedRef.current = true;
  }, []);

  const { data: scriptDraft } = useQuery({
    queryKey: ['script-draft'],
    queryFn: () => scriptApi.getDraft(),
    staleTime: 60_000,
  });

  const saveDraftMutation = useMutation({
    mutationFn: scriptApi.saveDraft,
  });

  useEffect(() => {
    if (!scriptDraft || isDraftHydratedRef.current || isDraftDirtyRef.current) return;
    const frame = window.requestAnimationFrame(() => {
      setVideoUrl(scriptDraft.source_video_url || '');
      setUserPrompt(scriptDraft.user_prompt || '');
      setSelectedPlanId(scriptDraft.plan_id || '');
      isDraftHydratedRef.current = true;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [scriptDraft]);

  useEffect(() => {
    if (!isDraftHydratedRef.current) return;
    const timer = window.setTimeout(() => {
      saveDraftMutation.mutate({
        source_video_url: videoUrl,
        user_prompt: userPrompt,
        plan_id: selectedPlanId || null,
      });
    }, 400);
    return () => window.clearTimeout(timer);
  }, [videoUrl, userPrompt, selectedPlanId, saveDraftMutation]);

  // 1. 提交拆解任务
  const createMutation = useMutation({
    mutationFn: (data: ExtractionCreateRequest) => scriptApi.createExtraction(data),
    onSuccess: (data) => {
      setActiveExtId(data.id);
      queryClient.invalidateQueries({ queryKey: ['extractions'] });
      notifySuccess('任务已创建，开始处理');
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`创建任务失败：${message}`);
    }
  });

  // 1.5 删除记录任务
  const deleteMutation = useMutation({
    mutationFn: (id: string) => scriptApi.deleteExtraction(id),
    onSuccess: (_, deletedId) => {
      if (activeExtId === deletedId) {
        setActiveExtId(null);
      }
      setDeleteConfirmId(null);
      queryClient.invalidateQueries({ queryKey: ['extractions'] });
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`删除失败：${message}`);
      setDeleteConfirmId(null);
    }
  });

  // 2. 轮询当前任务状态
  const { data: extraction } = useQuery({
    queryKey: ['extraction', activeExtId],
    queryFn: () => activeExtId ? scriptApi.getExtraction(activeExtId) : Promise.reject('No ID'),
    enabled: !!activeExtId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return (status === 'pending' || status === 'analyzing' || status === 'generating') ? 3000 : false;
    }
  });

  useEffect(() => {
    setIsEditingAnalysis(false);
    setEditedAnalysisTitle(extraction?.title || '');
    setEditedHighlightAnalysis(
      extraction?.highlight_analysis ? JSON.parse(JSON.stringify(extraction.highlight_analysis)) : null,
    );
    setIsEditingGeneratedScript(false);
    setEditedGeneratedScript(
      extraction?.generated_script ? JSON.parse(JSON.stringify(extraction.generated_script)) : null,
    );
  }, [extraction?.id]);

  // 3. 历史记录查询
  const { data: historyList } = useQuery({
    queryKey: ['extractions'],
    queryFn: () => scriptApi.listExtractions(0, 10),
    // 有任务在处理中时轮询列表，避免“最近任务”状态卡在旧值
    refetchInterval: (query) => {
      const list = (query.state.data as ExtractionListResponse[] | undefined) ?? [];
      const hasProcessing = list.some((item) =>
        item.status === 'pending' || item.status === 'analyzing' || item.status === 'generating'
      );
      return hasProcessing ? 3000 : false;
    },
  });

  // 4. 查询当前可用的账号策划列表
  const { data: plans } = useQuery({
    queryKey: ['planning-projects'],
    queryFn: () => planningApi.list(),
  });
  const completedPlans = plans?.filter(p => p.status === 'completed') || [];
  const completedHistory = historyList?.filter((h) => h.status === 'completed').length ?? 0;

  const saveGeneratedScriptMutation = useMutation({
    mutationFn: (generatedScript: ExtractionResponse['generated_script']) =>
      scriptApi.updateExtraction(activeExtId!, { generated_script: generatedScript || undefined }),
    onSuccess: (data) => {
      queryClient.setQueryData(['extraction', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['extractions'] });
      setEditedGeneratedScript(
        data.generated_script ? JSON.parse(JSON.stringify(data.generated_script)) : null,
      );
      setIsEditingGeneratedScript(false);
      notifySuccess('复刻脚本已保存');
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`保存失败：${message}`);
    },
  });

  const generateRemakeMutation = useMutation({
    mutationFn: (id: string) => scriptApi.generateRemake(id),
    onSuccess: (data) => {
      queryClient.setQueryData(['extraction', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['extractions'] });
      notifySuccess('复刻脚本任务已创建');
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`生成复刻脚本失败：${message}`);
    },
  });

  const updateGeneratedScriptField = <K extends keyof NonNullable<ExtractionResponse['generated_script']>>(
    key: K,
    value: NonNullable<ExtractionResponse['generated_script']>[K],
  ) => {
    setEditedGeneratedScript((current) => current ? { ...current, [key]: value } : current);
  };

  const updateStoryboardScene = (
    index: number,
    key: keyof NonNullable<ExtractionResponse['generated_script']>['storyboard'][number],
    value: string | number,
  ) => {
    setEditedGeneratedScript((current) => {
      if (!current?.storyboard) return current;
      const nextStoryboard = current.storyboard.map((scene, sceneIndex) =>
        sceneIndex === index ? { ...scene, [key]: value } : scene,
      );
      return { ...current, storyboard: nextStoryboard };
    });
  };

  const updateCopySegmentField = (
    index: number,
    key: keyof NonNullable<NonNullable<ExtractionResponse['highlight_analysis']>['copy_segment_breakdown']>[number],
    value: string,
  ) => {
    setEditedHighlightAnalysis((current) => {
      if (!current?.copy_segment_breakdown) return current;
      const nextSegments = current.copy_segment_breakdown.map((segment, segmentIndex) =>
        segmentIndex === index ? { ...segment, [key]: value } : segment,
      );
      return { ...current, copy_segment_breakdown: nextSegments };
    });
  };

  const retryExtractionWithSamePayload = useCallback((target: {
    id: string;
    source_video_url: string;
    user_prompt?: string;
    plan_id?: string | null;
  }, isAuto = false) => {
    const processing =
      extraction?.status === 'pending' ||
      extraction?.status === 'analyzing' ||
      extraction?.status === 'generating';
    if (createMutation.isPending || processing) return;

    const payload: ExtractionCreateRequest = {
      source_video_url: target.source_video_url,
      user_prompt: target.user_prompt || '',
      plan_id: target.plan_id ?? null,
    };

    autoRetriedExtractionIdsRef.current.add(target.id);
    createMutation.mutate(payload);
    if (isAuto) notifyInfo('任务失败，系统已自动重试一次');
    else notifyInfo('已按原参数重新创建拆解任务');
  }, [createMutation, extraction?.status]);

  const retryRemakeWithSameAnalysis = useCallback((targetId: string, isAuto = false) => {
    const processing =
      extraction?.status === 'pending' ||
      extraction?.status === 'analyzing' ||
      extraction?.status === 'generating';
    if (generateRemakeMutation.isPending || processing) return;

    autoRetriedExtractionIdsRef.current.add(targetId);
    generateRemakeMutation.mutate(targetId);
    if (isAuto) notifyInfo('复刻脚本生成失败，系统已自动重试一次');
    else notifyInfo('已按当前拆解结果重新生成复刻脚本');
  }, [extraction?.status, generateRemakeMutation]);

  useEffect(() => {
    if (!extraction || extraction.status !== 'failed') return;
    if (autoRetriedExtractionIdsRef.current.has(extraction.id)) return;
    if (!extraction.error_message || !TRANSIENT_FAILURE_PATTERN.test(extraction.error_message)) return;

    const timer = window.setTimeout(() => {
      if (extraction.has_highlight_analysis) retryRemakeWithSameAnalysis(extraction.id, true);
      else retryExtractionWithSamePayload(extraction, true);
    }, 1200);

    return () => window.clearTimeout(timer);
  }, [extraction, retryExtractionWithSamePayload, retryRemakeWithSameAnalysis]);

  // 轮询详情时，同步刷新“最近任务”中的对应状态，避免列表状态滞后
  useEffect(() => {
    if (!extraction) return;
    queryClient.setQueryData<ExtractionListResponse[] | undefined>(['extractions'], (prev) => {
      if (!prev || prev.length === 0) return prev;
      let touched = false;
      const next = prev.map((item) => {
        if (item.id !== extraction.id) return item;
        touched = true;
        return {
          ...item,
          status: extraction.status,
          title: extraction.title || item.title,
          cover_url: extraction.cover_url || item.cover_url,
          has_highlight_analysis: extraction.has_highlight_analysis,
          has_generated_script: extraction.has_generated_script,
          retry_count: extraction.retry_count ?? item.retry_count,
          max_retries: extraction.max_retries ?? item.max_retries,
        };
      });
      return touched ? next : prev;
    });

    if (extraction.status === 'completed' || extraction.status === 'failed') {
      queryClient.invalidateQueries({ queryKey: ['extractions'] });
    }
  }, [extraction, queryClient]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoUrl) return;
    createMutation.mutate({
      source_video_url: videoUrl,
      user_prompt: userPrompt,
      plan_id: selectedPlanId ? selectedPlanId : null
    });
  };

  const getStatusText = (status: ExtractionStatus | undefined) => {
    switch (status) {
      case 'pending': return '任务排队中';
      case 'analyzing': return '正在解析原视频并提取亮点';
      case 'generating': return '正在生成复刻脚本';
      case 'completed': return extraction?.generated_script ? '复刻脚本生成完成' : '源视频拆解完成，待生成复刻脚本';
      case 'failed': return '任务失败，请调整后重试';
      default: return '';
    }
  };

  const getHistoryStatusText = (item: ExtractionListResponse) => {
    const status = item.status;
    switch (status) {
      case 'pending': return '排队中';
      case 'analyzing': return '解析中';
      case 'generating': return '生成中';
      case 'completed': return item.has_generated_script ? '已复刻' : '已拆解';
      case 'failed': return '失败';
      default: return status;
    }
  };

  const isProcessing = extraction?.status === 'pending' || extraction?.status === 'analyzing' || extraction?.status === 'generating';
  const hasAnalysis = Boolean(extraction?.highlight_analysis || extraction?.has_highlight_analysis);
  const hasGeneratedScript = Boolean(extraction?.generated_script || extraction?.has_generated_script);
  const analysisTitleForExport = (isEditingAnalysis ? editedAnalysisTitle : extraction?.title) || '未命名视频';
  const analysisExportBaseName = sanitizeFilename(analysisTitleForExport || extraction?.source_video_url || 'source-analysis');
  const analysisForExport = isEditingAnalysis && editedHighlightAnalysis
    ? editedHighlightAnalysis
    : extraction?.highlight_analysis;

  const handleExportAnalysisLongImage = async () => {
    if (!analysisForExport || isExportingAnalysis) return;
    if (!analysisExportRef.current) {
      notifyInfo('当前还没有可导出的拆解内容');
      return;
    }

    try {
      setIsExportingAnalysis(true);
      notifyInfo('正在生成拆解长图，请稍等');
      if (typeof document !== 'undefined' && 'fonts' in document) {
        await (document as Document & { fonts?: FontFaceSet }).fonts?.ready;
      }
      await sleep(80);

      const dataUrl = await toPng(analysisExportRef.current, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: '#f8fafc',
      });

      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${analysisExportBaseName}-源视频拆解长图.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifySuccess('已导出源视频拆解长图');
    } catch (error) {
      notifyError(`导出拆解长图失败：${(error as Error).message || '请稍后再试'}`);
    } finally {
      setIsExportingAnalysis(false);
    }
  };

  return (
    <div className="script-ext-container">
      <section className="script-ext-hero">
        <div>
          <div className="script-ext-hero-pill"><Wand2 size={13} /> Script Remake</div>
          <h1>脚本拆解与复刻</h1>
          <p>先拆清楚源视频为什么有效，再决定是否基于拆解结果生成适配你账号定位的新脚本。</p>
        </div>
        <div className="script-ext-hero-stats">
          <div className="script-ext-stat">
            <span>历史任务</span>
            <strong>{historyList?.length ?? 0}</strong>
          </div>
          <div className="script-ext-stat">
            <span>已完成</span>
            <strong>{completedHistory}</strong>
          </div>
          <div className="script-ext-stat">
            <span>可关联策划</span>
            <strong>{completedPlans.length}</strong>
          </div>
        </div>
      </section>

      <div className="ext-main">
        {/* 左侧：输入控制台与历史 */}
        <div className="ext-sidebar">
          <form className="ext-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label><Link2 size={16} className="text-primary-500" /> 源视频链接</label>
              <input
                type="text"
                placeholder="例如：https://v.douyin.com/xxxxx/"
                value={videoUrl}
                onChange={(e) => {
                  markDraftDirty();
                  setVideoUrl(e.target.value);
                }}
                required
              />
            </div>

            <div className="form-group">
              <label><Users size={16} className="text-primary-500" /> 关联策划项目 <span className="label-badge">推荐</span></label>
              <div className="custom-select-container" ref={dropdownRef}>
                <div
                  className={`custom-select-header ${isDropdownOpen ? 'open' : ''}`}
                  onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                >
                  <span className={selectedPlanId ? 'selected-text' : 'placeholder-text'}>
                    {selectedPlanId && completedPlans.length > 0
                      ? completedPlans.find(p => p.id === selectedPlanId)?.client_name + ' - ' + completedPlans.find(p => p.id === selectedPlanId)?.industry
                      : '不关联项目（仅基础拆解）'}
                  </span>
                  <ChevronDown className="dropdown-icon" size={16} />
                </div>

                {isDropdownOpen && (
                  <div className="custom-select-dropdown">
                    <div
                      className={`custom-select-option ${selectedPlanId === '' ? 'selected' : ''}`}
                      onClick={() => {
                        markDraftDirty();
                        setSelectedPlanId('');
                        setIsDropdownOpen(false);
                      }}
                    >
                      不关联项目（仅基础拆解）
                    </div>
                    {completedPlans.map(plan => (
                      <div
                        key={plan.id}
                        className={`custom-select-option ${selectedPlanId === plan.id ? 'selected' : ''}`}
                        onClick={() => {
                          markDraftDirty();
                          setSelectedPlanId(plan.id);
                          setIsDropdownOpen(false);
                        }}
                      >
                        {plan.client_name} - {plan.industry}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <p style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                选择项目后，系统会自动读取该项目的增长策略与目标受众信息，后续生成复刻脚本时会更贴合门店定位。
              </p>
            </div>

            <div className="form-group">
              <label><FileEdit size={16} className="text-primary-500" /> 补充改写要求 <span className="label-optional">可选</span></label>
              <textarea
                rows={3}
                placeholder="例如：语气更干练、节奏更快、结尾强调评论互动。"
                value={userPrompt}
                onChange={(e) => {
                  markDraftDirty();
                  setUserPrompt(e.target.value);
                }}
              />
              <p style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
                输入内容会自动保存到数据库草稿，换设备登录也不会丢失。
              </p>
            </div>

            <button
              type="submit"
              className="ext-submit-btn"
              disabled={createMutation.isPending || isProcessing}
            >
              {createMutation.isPending ? '正在创建任务...' : (isProcessing ? '任务处理中...' : (
                <>
                  <Sparkles size={16} /> 开始拆解
                </>
              ))}
            </button>
          </form>

          {historyList && historyList.length > 0 && (
            <div className="ext-history">
              <h3 className="flex items-center gap-2"><Clock size={16} /> 最近任务</h3>
              <div className="history-list">
                {historyList.map(item => (
                  <div
                    key={item.id}
                    className={`history-card ${activeExtId === item.id ? 'active' : ''}`}
                    onClick={() => setActiveExtId(item.id)}
                  >
                    <div className="history-title" title={item.title}>
                      <PlayCircle size={14} className="history-icon" />
                      {item.title || '正在解析标题...'}
                    </div>
                    <div className="history-card-footer">
                      <div className="history-status status-badge" data-status={item.status}>
                        {getHistoryStatusText(item)}
                      </div>
                      <div className="history-actions">
                        {item.status === 'completed' && item.source_video_url && (
                          <a
                            href={extractUrl(item.source_video_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="history-action-btn"
                            title="查看原视频"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink size={14} />
                          </a>
                        )}
                        <button
                          className="history-action-btn history-delete-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmId(item.id);
                          }}
                          title="删除该记录"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 右侧：结果展示区 */}
        <div className="ext-content">
          {!extraction ? (
            <div className="content-placeholder">
              <WaitingSmileFace />
              <h3>等待开始任务</h3>
              <p>在左侧输入视频链接并设置改写要求，系统会先完成源视频拆解；拆解完成后，你再决定是否生成复刻脚本。</p>
            </div>
          ) : (
            <div className="result-container">
              {/* 顶部状态栏 */}
              <div className="status-bar" data-status={extraction.status}>
                <div className="status-text">
                  {isProcessing && <RefreshCw size={16} className="spin-icon" />}
                  {getStatusText(extraction.status)}
                </div>
                <div className="status-actions">
                  {(extraction.retry_count ?? 0) > 0 && (
                    <div className="retry-count-badge">
                      已重试 {extraction.retry_count}/{extraction.max_retries ?? 1}
                    </div>
                  )}
                  {extraction.status === 'failed' && (
                    <button
                      type="button"
                      className="status-retry-btn"
                      disabled={createMutation.isPending || generateRemakeMutation.isPending || isProcessing}
                      onClick={() => {
                        if (extraction.has_highlight_analysis) retryRemakeWithSameAnalysis(extraction.id);
                        else retryExtractionWithSamePayload(extraction);
                      }}
                    >
                      <RefreshCw size={13} /> 一键重试
                    </button>
                  )}
                  {extraction.error_message && (
                    <div className="error-text"><AlertCircle size={14} /> {extraction.error_message}</div>
                  )}
                </div>
              </div>

              {hasAnalysis && (
                <div className="result-split-view">
                  {/* 左版块：源视频信息与拆解 */}
                  <div className="source-analysis-pane">
                    <div className="pane-header">
                      <div>
                        <h2 className="pane-title">源视频拆解结果</h2>
                        <p className="pane-subtitle">支持临时修改逐段文案拆解，并导出长图；关闭弹窗后不会改动原文案。</p>
                      </div>
                      {extraction.highlight_analysis && (
                        <div className="pane-header-actions">
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={handleExportAnalysisLongImage}
                            disabled={isEditingAnalysis || isExportingAnalysis}
                          >
                            <Download size={14} /> {isExportingAnalysis ? '导出中...' : '导出长图'}
                          </button>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => {
                              setEditedAnalysisTitle(extraction.title || '');
                              setEditedHighlightAnalysis(
                                extraction.highlight_analysis
                                  ? JSON.parse(JSON.stringify(extraction.highlight_analysis))
                                  : null,
                              );
                              setIsEditingAnalysis(true);
                            }}
                          >
                            <Pencil size={14} /> 编辑逐段文案
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="source-meta">
                      {extraction.cover_url && (
                        <img src={extraction.cover_url} alt="Cover" className="source-cover" />
                      )}
                      <div className="source-info">
                        <h3>{extraction.title}</h3>
                        <p>{extraction.description}</p>
                        {extraction.source_video_url && (
                          <a
                            href={extractUrl(extraction.source_video_url)}
                            target="_blank"
                            rel="noreferrer"
                            className="view-source-btn"
                          >
                            <ExternalLink size={14} /> 查看源视频
                          </a>
                        )}
                      </div>
                    </div>

                    {extraction.highlight_analysis && (
                      <div className="highlight-cards">
                        <div className="hl-card">
                          <label>核心主题</label>
                          <div>{extraction.highlight_analysis.core_theme}</div>
                        </div>
                        <div className="hl-card">
                          <label>爆款结构</label>
                          <div>{extraction.highlight_analysis.success_structure}</div>
                        </div>
                        <div className="hl-card">
                          <label>钩子机制</label>
                          <div>{extraction.highlight_analysis.hook_mechanism}</div>
                        </div>
                        <div className="hl-card">
                          <label>文案风格</label>
                          <div>{extraction.highlight_analysis.copywriting_style}</div>
                        </div>
                        <div className="hl-card hl-card-full">
                          <label>视觉节奏</label>
                          <div>{extraction.highlight_analysis.visual_rhythm}</div>
                        </div>
                        <div className="hl-card hl-card-full">
                          <label>声音与情绪</label>
                          <div>{extraction.highlight_analysis.audio_emotion}</div>
                        </div>
                      </div>
                    )}

                    {extraction.highlight_analysis?.copy_segment_breakdown?.length ? (
                      <div className="source-copy-breakdown">
                        <h3>逐段文案拆解</h3>
                        <div className="source-copy-breakdown-list">
                          {extraction.highlight_analysis.copy_segment_breakdown.map((segment, idx) => (
                            <div key={`${segment.segment}-${idx}`} className="copy-breakdown-card">
                              <div className="copy-breakdown-head">
                                <div className="copy-breakdown-title">{segment.segment || `第 ${idx + 1} 段`}</div>
                                {segment.duration && (
                                  <div className="copy-breakdown-duration">{segment.duration}</div>
                                )}
                              </div>
                              <div className="copy-breakdown-body">
                                <div className="detail-row">
                                  <span className="row-label">原段文案</span>
                                  <span className="row-text copy-breakdown-script">“{segment.original_copy}”</span>
                                </div>
                                <div className="detail-row">
                                  <span className="row-label">作用</span>
                                  <span className="row-text">{segment.copy_function}</span>
                                </div>
                                {segment.emotion_goal && (
                                  <div className="detail-row">
                                    <span className="row-label">情绪目标</span>
                                    <span className="row-text">{segment.emotion_goal}</span>
                                  </div>
                                )}
                                {segment.transition_role && (
                                  <div className="detail-row">
                                    <span className="row-label">承接方式</span>
                                    <span className="row-text">{segment.transition_role}</span>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {analysisForExport && (
                      <div className="analysis-export-canvas-wrap" aria-hidden="true">
                        <div ref={analysisExportRef} className="analysis-export-long">
                          <div className="analysis-export-header">
                            <div className="analysis-export-pill">源视频拆解长图</div>
                            <h2>{analysisTitleForExport}</h2>
                          </div>

                          {analysisForExport.copy_segment_breakdown?.length ? (
                            <div className="analysis-export-segments">
                              <h3>逐段文案拆解</h3>
                              {analysisForExport.copy_segment_breakdown.map((segment, idx) => (
                                <div key={`${segment.segment}-${idx}`} className="analysis-export-segment-card">
                                  <div className="analysis-export-segment-head">
                                    <strong>{segment.segment || `第 ${idx + 1} 段`}</strong>
                                    {segment.duration && <span>{segment.duration}</span>}
                                  </div>
                                  <div className="analysis-export-segment-body">
                                    <div>
                                      <label>原段文案</label>
                                      <p>{segment.original_copy}</p>
                                    </div>
                                    <div>
                                      <label>作用</label>
                                      <p>{segment.copy_function}</p>
                                    </div>
                                    {segment.emotion_goal && (
                                      <div>
                                        <label>情绪目标</label>
                                        <p>{segment.emotion_goal}</p>
                                      </div>
                                    )}
                                    {segment.transition_role && (
                                      <div>
                                        <label>承接方式</label>
                                        <p>{segment.transition_role}</p>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 右版块：生成的复刻脚本 */}
                  <div className="generated-script-pane">
                    <div className="pane-header">
                      <div>
                        <h2 className="pane-title">复刻脚本结果</h2>
                        <p className="pane-subtitle">拆解完成后，再决定是否进入复刻生成。</p>
                      </div>
                      {hasGeneratedScript && extraction.generated_script && (
                        <div className="pane-header-actions">
                          {isEditingGeneratedScript ? (
                            <>
                              <button
                                className="btn btn-primary btn-sm"
                                disabled={saveGeneratedScriptMutation.isPending || !editedGeneratedScript}
                                onClick={() => editedGeneratedScript && saveGeneratedScriptMutation.mutate(editedGeneratedScript)}
                              >
                                <Save size={14} /> {saveGeneratedScriptMutation.isPending ? '保存中...' : '保存'}
                              </button>
                              <button
                                className="btn btn-ghost btn-sm"
                                disabled={saveGeneratedScriptMutation.isPending}
                                onClick={() => {
                                  setEditedGeneratedScript(
                                    extraction.generated_script
                                      ? JSON.parse(JSON.stringify(extraction.generated_script))
                                      : null,
                                  );
                                  setIsEditingGeneratedScript(false);
                                }}
                              >
                                <X size={14} /> 取消
                              </button>
                            </>
                          ) : (
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => {
                                setEditedGeneratedScript(
                                  extraction.generated_script
                                    ? JSON.parse(JSON.stringify(extraction.generated_script))
                                    : null,
                                );
                                setIsEditingGeneratedScript(true);
                              }}
                            >
                              <FileEdit size={14} /> 编辑脚本
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {!hasGeneratedScript && extraction.status !== 'generating' && (
                      <div className="remake-empty-state">
                        <div className="remake-empty-state-badge">第二步</div>
                        <h3>基于拆解结果生成复刻脚本</h3>
                        <p>现在已经拆清楚这条视频的结构、文案节奏和情绪推进。你可以直接基于这份拆解结果，生成新的可拍脚本。</p>
                        <button
                          type="button"
                          className="ext-submit-btn remake-generate-btn"
                          disabled={generateRemakeMutation.isPending || isProcessing}
                          onClick={() => activeExtId && generateRemakeMutation.mutate(activeExtId)}
                        >
                          {generateRemakeMutation.isPending ? '正在创建复刻任务...' : (
                            <>
                              <Sparkles size={16} /> 生成复刻脚本
                            </>
                          )}
                        </button>
                      </div>
                    )}

                    {!hasGeneratedScript && extraction.status === 'generating' && (
                      <div className="remake-empty-state remake-loading-state">
                        <RefreshCw size={18} className="spin-icon" />
                        <h3>正在生成复刻脚本</h3>
                        <p>拆解结果已经固定，系统正在基于这份分析生成新的脚本结构和分镜。</p>
                      </div>
                    )}

                    {hasGeneratedScript && extraction.generated_script && (
                      <div className="script-content">
                        <div className="script-summary">
                          <h3>新视频切入点</h3>
                          {isEditingGeneratedScript && editedGeneratedScript ? (
                            <div className="script-edit-fields">
                              <label className="script-edit-field">
                                <span>建议标题</span>
                                <textarea
                                  className="form-input form-textarea"
                                  rows={2}
                                  value={editedGeneratedScript.title_suggestion || ''}
                                  onChange={(e) => updateGeneratedScriptField('title_suggestion', e.target.value)}
                                />
                              </label>
                              <label className="script-edit-field">
                                <span>吸睛开头</span>
                                <textarea
                                  className="form-input form-textarea"
                                  rows={2}
                                  value={editedGeneratedScript.opening_hook || ''}
                                  onChange={(e) => updateGeneratedScriptField('opening_hook', e.target.value)}
                                />
                              </label>
                              <label className="script-edit-field">
                                <span>中段方案</span>
                                <textarea
                                  className="form-input form-textarea"
                                  rows={4}
                                  value={editedGeneratedScript.middle_body || ''}
                                  onChange={(e) => updateGeneratedScriptField('middle_body', e.target.value)}
                                />
                              </label>
                              <label className="script-edit-field">
                                <span>结尾引导</span>
                                <textarea
                                  className="form-input form-textarea"
                                  rows={2}
                                  value={editedGeneratedScript.ending_call || ''}
                                  onChange={(e) => updateGeneratedScriptField('ending_call', e.target.value)}
                                />
                              </label>
                            </div>
                          ) : (
                            <>
                              <div><strong>建议标题：</strong>{extraction.generated_script.title_suggestion}</div>
                              <div><strong>吸睛开头：</strong>{extraction.generated_script.opening_hook}</div>
                              {extraction.generated_script.middle_body && (
                                <div><strong>中段方案：</strong>{extraction.generated_script.middle_body}</div>
                              )}
                              <div><strong>结尾引导：</strong>{extraction.generated_script.ending_call}</div>
                            </>
                          )}
                        </div>

                        <div className="script-storyboard">
                          <h3>详细分镜</h3>
                          {(isEditingGeneratedScript ? editedGeneratedScript?.storyboard : extraction.generated_script.storyboard)?.map((scene, idx) => (
                            <div key={idx} className="scene-card">
                              <div className="scene-index">场景 {scene.scene} {scene.duration && `(${scene.duration})`}</div>
                              {isEditingGeneratedScript && editedGeneratedScript ? (
                                <div className="scene-details scene-edit-fields">
                                  <label className="script-edit-field">
                                    <span>时长</span>
                                    <input
                                      className="form-input"
                                      value={scene.duration || ''}
                                      onChange={(e) => updateStoryboardScene(idx, 'duration', e.target.value)}
                                    />
                                  </label>
                                  <label className="script-edit-field">
                                    <span>画面</span>
                                    <textarea
                                      className="form-input form-textarea"
                                      rows={2}
                                      value={scene.visual || ''}
                                      onChange={(e) => updateStoryboardScene(idx, 'visual', e.target.value)}
                                    />
                                  </label>
                                  <label className="script-edit-field">
                                    <span>机位</span>
                                    <input
                                      className="form-input"
                                      value={scene.camera || ''}
                                      onChange={(e) => updateStoryboardScene(idx, 'camera', e.target.value)}
                                    />
                                  </label>
                                  <label className="script-edit-field">
                                    <span>情绪/节奏</span>
                                    <textarea
                                      className="form-input form-textarea"
                                      rows={2}
                                      value={scene.emotion_beat || ''}
                                      onChange={(e) => updateStoryboardScene(idx, 'emotion_beat', e.target.value)}
                                    />
                                  </label>
                                  <label className="script-edit-field">
                                    <span>台词配音</span>
                                    <textarea
                                      className="form-input form-textarea"
                                      rows={3}
                                      value={scene.script || ''}
                                      onChange={(e) => updateStoryboardScene(idx, 'script', e.target.value)}
                                    />
                                  </label>
                                </div>
                              ) : (
                                <div className="scene-details">
                                  <div className="detail-row">
                                    <span className="row-label">画面/机位</span>
                                    <span className="row-text" style={{ fontFamily: 'monospace', color: 'var(--primary-500)' }}>
                                      {scene.visual} ({scene.camera})
                                    </span>
                                  </div>
                                  <div className="detail-row">
                                    <span className="row-label">情绪/节奏</span>
                                    <span className="row-text text-muted">{scene.emotion_beat}</span>
                                  </div>
                                  <div className="detail-row">
                                    <span className="row-label">台词配音</span>
                                    <span className="row-text" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                                      "{scene.script}"
                                    </span>
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>

                        {(isEditingGeneratedScript ? editedGeneratedScript?.optimization_tips : extraction.generated_script.optimization_tips) && (
                          <div className="script-tips">
                            <h3>优化建议</h3>
                            {isEditingGeneratedScript && editedGeneratedScript ? (
                              <textarea
                                className="form-input form-textarea"
                                rows={5}
                                value={(editedGeneratedScript.optimization_tips || []).join('\n')}
                                onChange={(e) =>
                                  updateGeneratedScriptField(
                                    'optimization_tips',
                                    e.target.value
                                      .split('\n')
                                      .map((item) => item.trim())
                                      .filter(Boolean),
                                  )
                                }
                                placeholder="每行一条优化建议"
                              />
                            ) : (
                              <ul>
                                {extraction.generated_script.optimization_tips.map((tip, idx) => (
                                  <li key={idx}>{tip}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {isEditingAnalysis && editedHighlightAnalysis && (
        <div className="ext-modal-overlay">
          <div className="ext-modal ext-modal-large">
            <div className="analysis-edit-modal-header">
              <div>
                <h3 className="ext-modal-title">编辑逐段文案拆解</h3>
                <p className="ext-modal-desc">这里的修改只用于当前次导出长图。关闭弹窗或离开页面后，不会覆盖原拆解文案。</p>
              </div>
              <div className="analysis-edit-modal-actions">
                <button
                  className="btn btn-primary btn-sm"
                  disabled={isExportingAnalysis || !editedHighlightAnalysis}
                  onClick={handleExportAnalysisLongImage}
                >
                  <Download size={14} /> {isExportingAnalysis ? '导出中...' : '导出长图'}
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={isExportingAnalysis}
                  onClick={() => {
                    setEditedAnalysisTitle(extraction?.title || '');
                    setEditedHighlightAnalysis(
                      extraction?.highlight_analysis ? JSON.parse(JSON.stringify(extraction.highlight_analysis)) : null,
                    );
                    setIsEditingAnalysis(false);
                  }}
                >
                  <X size={14} /> 取消
                </button>
              </div>
            </div>

            <div className="analysis-edit-modal-body">
              <label className="script-edit-field">
                <span>导出标题</span>
                <input
                  className="form-input"
                  value={editedAnalysisTitle}
                  onChange={(e) => setEditedAnalysisTitle(e.target.value)}
                  placeholder="请输入导出长图标题"
                />
              </label>
              {editedHighlightAnalysis.copy_segment_breakdown?.length ? (
                <div className="analysis-edit-sections">
                  <h4>逐段文案拆解</h4>
                  {editedHighlightAnalysis.copy_segment_breakdown.map((segment, idx) => (
                    <div key={`${segment.segment}-${idx}`} className="analysis-edit-segment-card">
                      <div className="analysis-edit-segment-title">{segment.segment || `第 ${idx + 1} 段`}</div>
                      <label className="script-edit-field">
                        <span>阶段名称</span>
                        <input
                          className="form-input"
                          value={segment.segment || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'segment', e.target.value)}
                        />
                      </label>
                      <label className="script-edit-field">
                        <span>时长区间</span>
                        <input
                          className="form-input"
                          value={segment.duration || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'duration', e.target.value)}
                        />
                      </label>
                      <label className="script-edit-field">
                        <span>原段文案</span>
                        <textarea
                          className="form-input form-textarea"
                          rows={3}
                          value={segment.original_copy || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'original_copy', e.target.value)}
                        />
                      </label>
                      <label className="script-edit-field">
                        <span>作用</span>
                        <textarea
                          className="form-input form-textarea"
                          rows={2}
                          value={segment.copy_function || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'copy_function', e.target.value)}
                        />
                      </label>
                      <label className="script-edit-field">
                        <span>情绪目标</span>
                        <textarea
                          className="form-input form-textarea"
                          rows={2}
                          value={segment.emotion_goal || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'emotion_goal', e.target.value)}
                        />
                      </label>
                      <label className="script-edit-field">
                        <span>承接方式</span>
                        <textarea
                          className="form-input form-textarea"
                          rows={2}
                          value={segment.transition_role || ''}
                          onChange={(e) => updateCopySegmentField(idx, 'transition_role', e.target.value)}
                        />
                      </label>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="analysis-edit-empty">当前没有逐段文案拆解可编辑。</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteConfirmId && (
        <div className="ext-modal-overlay">
          <div className="ext-modal">
            <h3 className="ext-modal-title">确认删除</h3>
            <p className="ext-modal-desc">确认删除这条任务记录吗？删除后无法恢复。</p>
            <div className="ext-modal-actions">
              <button
                className="ext-btn-cancel"
                onClick={() => setDeleteConfirmId(null)}
                disabled={deleteMutation.isPending}
              >
                取消
              </button>
              <button
                className="ext-btn-danger"
                onClick={() => {
                  deleteMutation.mutate(deleteConfirmId);
                }}
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
