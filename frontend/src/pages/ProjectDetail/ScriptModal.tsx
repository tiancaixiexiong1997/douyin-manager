import { useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toPng } from 'html-to-image';
import { planningApi, type ContentItem, type TaskCenterItem, type VideoScript } from '../../api/client';
import { Download, FileText, Loader2, Pencil, Save, Sparkles, X } from '../../components/Icons';
import { notifyError, notifyInfo, notifySuccess } from '../../utils/notify';

type ScriptTaskStatus = TaskCenterItem['status'] | null;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function sanitizeFilename(value: string): string {
  return value
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80) || 'script';
}

export function ScriptModal({
  item,
  projectId,
  taskStatus,
  taskMessage,
  onClose,
}: {
  item: ContentItem;
  projectId: string;
  taskStatus: ScriptTaskStatus;
  taskMessage?: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [script, setScript] = useState<VideoScript | null>(item.full_script || null);
  const [isEditing, setIsEditing] = useState(false);
  const [editScript, setEditScript] = useState<VideoScript | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const exportImageRef = useRef<HTMLDivElement | null>(null);
  const isTaskRunning = taskStatus === 'queued' || taskStatus === 'running';

  const generateMutation = useMutation({
    mutationFn: () => planningApi.generateScript(item.id),
    onSuccess: (data) => {
      setScript(data.script);
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      qc.invalidateQueries({ queryKey: ['content-script-tasks', projectId] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (nextScript: VideoScript) => planningApi.updateContentItem(item.id, { full_script: nextScript }),
    onSuccess: () => {
      setScript(editScript);
      setIsEditing(false);
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const startEdit = () => {
    setEditScript(JSON.parse(JSON.stringify(script)));
    setIsEditing(true);
  };

  const exportBaseName = useMemo(
    () => sanitizeFilename(`第${item.day_number}天-${item.title_direction}`),
    [item.day_number, item.title_direction],
  );

  const handleExportLongImage = async () => {
    if (!script || isEditing || isExporting) return;
    if (!exportImageRef.current) {
      notifyInfo('当前还没有可导出的脚本内容');
      return;
    }

    try {
      setIsExporting(true);
      notifyInfo('正在生成脚本图片，请稍等');
      if (typeof document !== 'undefined' && 'fonts' in document) {
        await (document as Document & { fonts?: FontFaceSet }).fonts?.ready;
      }
      await sleep(80);

      const dataUrl = await toPng(exportImageRef.current, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: '#f8fafc',
      });

      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${exportBaseName}-完整脚本长图.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      notifySuccess('已导出完整脚本长图');
    } catch (error) {
      notifyError(`导出脚本长图失败：${(error as Error).message || '请稍后再试'}`);
    } finally {
      setIsExporting(false);
    }
  };

  return createPortal(
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal script-modal animate-scale-in" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">第 {item.day_number} 天内容</h2>
            <p className="page-subtitle" style={{ marginTop: 4 }}>{item.title_direction}</p>
          </div>
          <div className="flex items-center gap-2">
            {script && !isEditing && (
              <button className="btn btn-ghost btn-sm" onClick={handleExportLongImage} disabled={isExporting}>
                <Download size={13} /> {isExporting ? '导出中...' : '导出脚本长图'}
              </button>
            )}
            {script && !isEditing && (
              <button className="btn btn-ghost btn-sm" onClick={startEdit}>
                <Pencil size={13} /> 编辑
              </button>
            )}
            {isEditing && (
              <>
                <button
                  className="btn btn-primary btn-sm"
                  disabled={saveMutation.isPending}
                  onClick={() => editScript && saveMutation.mutate(editScript)}
                >
                  <Save size={13} /> {saveMutation.isPending ? '保存中...' : '保存'}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => setIsEditing(false)}>
                  <X size={13} /> 取消
                </button>
              </>
            )}
            <button className="btn btn-icon btn-ghost" onClick={onClose}><X size={16} /></button>
          </div>
        </div>

        {!script && !generateMutation.isPending && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <div className="empty-icon" style={{ margin: '0 auto 16px' }}>
              <FileText size={24} />
            </div>
            <p className="text-secondary" style={{ marginBottom: 20 }}>
              点击下方按钮，AI 将根据账号定位和参考博主风格，生成完整视频脚本
            </p>
            {isTaskRunning ? (
              <div className="text-secondary" style={{ fontSize: 13 }}>
                已有脚本任务在后台执行中，请稍后自动刷新查看。
              </div>
            ) : (
              <button className="btn btn-primary" onClick={() => generateMutation.mutate()}>
                <Sparkles size={15} /> 生成完整脚本
              </button>
            )}
          </div>
        )}

        {(generateMutation.isPending || isTaskRunning) && (
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Loader2 size={32} className="text-secondary" style={{ animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
            <p className="text-secondary">{taskMessage || 'AI 正在为你生成脚本，请稍等...'}</p>
          </div>
        )}

        {generateMutation.isError && (
          <div className="error-tip" style={{ marginBottom: 12 }}>
            {(generateMutation.error as Error).message}
          </div>
        )}

        {script && !isEditing && (
          <div className="script-content animate-fade-in">
            {script.title_options && (
              <div className="script-section">
                <div className="script-section-title">📝 标题备选</div>
                <div className="title-options">
                  {script.title_options.map((title, index) => (
                    <div key={index} className="title-option">{title}</div>
                  ))}
                </div>
              </div>
            )}
            {script.hook_script && (
              <div className="script-section">
                <div className="script-section-title">⚡ 黄金3秒开头</div>
                <div className="script-text">{script.hook_script}</div>
              </div>
            )}
            {script.storyboard && (
              <div className="script-section">
                <div className="script-section-title">🎬 分镜脚本</div>
                <div className="storyboard">
                  {script.storyboard.map((scene) => (
                    <div key={scene.scene} className="storyboard-scene">
                      <div className="scene-header">
                        <span className="scene-num">Scene {scene.scene}</span>
                        <span className="scene-duration">{scene.duration}</span>
                      </div>
                      <div className="scene-body">
                        <div className="scene-row"><span className="scene-label">画面</span>{scene.visual}</div>
                        <div className="scene-row"><span className="scene-label">台词</span>{scene.script}</div>
                        <div className="scene-row"><span className="scene-label">拍摄</span>{scene.camera}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {script.caption_template && (
              <div className="script-section">
                <div className="script-section-title">📱 发布文案</div>
                <div className="script-text">{script.caption_template}</div>
              </div>
            )}
            {script.hashtag_suggestions && (
              <div className="script-section">
                <div className="script-section-title">🏷️ 话题标签</div>
                <div className="hashtags">
                  {script.hashtag_suggestions.map((tag) => (
                    <span key={tag} className="badge badge-purple">#{tag}</span>
                  ))}
                </div>
              </div>
            )}
            <div className="modal-footer" style={{ justifyContent: 'center' }}>
              <button className="btn btn-ghost btn-sm" onClick={() => generateMutation.mutate()} disabled={isTaskRunning || generateMutation.isPending}>
                <Sparkles size={13} /> 重新生成
              </button>
            </div>
          </div>
        )}

        {isEditing && editScript && (
          <div className="script-content animate-fade-in">
            <div className="script-section">
              <div className="script-section-title">📝 标题备选</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={3}
                value={editScript.title_options?.join('\n') || ''}
                onChange={(event) => setEditScript((current) => ({ ...current!, title_options: event.target.value.split('\n') }))}
                placeholder="每行一个标题"
              />
            </div>
            <div className="script-section">
              <div className="script-section-title">⚡ 黄金3秒开头</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={3}
                value={editScript.hook_script || ''}
                onChange={(event) => setEditScript((current) => ({ ...current!, hook_script: event.target.value }))}
              />
            </div>
            {editScript.storyboard && (
              <div className="script-section">
                <div className="script-section-title">🎬 分镜脚本</div>
                <div className="storyboard">
                  {editScript.storyboard.map((scene, index) => (
                    <div key={scene.scene} className="storyboard-scene">
                      <div className="scene-header">
                        <span className="scene-num">Scene {scene.scene}</span>
                        <input className="form-input" style={{ fontSize: 12, padding: '2px 8px', width: 80 }}
                          value={scene.duration}
                          onChange={(event) => setEditScript((current) => {
                            const storyboard = [...(current!.storyboard || [])];
                            storyboard[index] = { ...storyboard[index], duration: event.target.value };
                            return { ...current!, storyboard };
                          })}
                        />
                      </div>
                      <div className="scene-body">
                        {(['visual', 'script', 'camera'] as const).map((field) => (
                          <div key={field} className="scene-row">
                            <span className="scene-label">{{ visual: '画面', script: '台词', camera: '拍摄' }[field]}</span>
                            <textarea className="form-input" style={{ fontSize: 12, flex: 1 }} rows={2}
                              value={scene[field]}
                              onChange={(event) => setEditScript((current) => {
                                const storyboard = [...(current!.storyboard || [])];
                                storyboard[index] = { ...storyboard[index], [field]: event.target.value };
                                return { ...current!, storyboard };
                              })}
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="script-section">
              <div className="script-section-title">📱 发布文案</div>
              <textarea className="form-input form-textarea" style={{ fontSize: 13 }} rows={4}
                value={editScript.caption_template || ''}
                onChange={(event) => setEditScript((current) => ({ ...current!, caption_template: event.target.value }))}
              />
            </div>
            <div className="script-section">
              <div className="script-section-title">🏷️ 话题标签</div>
              <textarea className="form-input" style={{ fontSize: 13 }} rows={2}
                value={editScript.hashtag_suggestions?.join(' ') || ''}
                onChange={(event) => setEditScript((current) => ({ ...current!, hashtag_suggestions: event.target.value.split(/\\s+/).filter(Boolean) }))}
                placeholder="空格分隔，不需要加 #"
              />
            </div>
          </div>
        )}

        {script && !isEditing && (
          <div className="script-export-canvas" aria-hidden="true">
            <div ref={exportImageRef} className="script-export-long">
              <div className="script-export-topbar">
                <span className="script-export-topbar-badge">完整脚本</span>
                <span className="script-export-topbar-meta">第 {item.day_number} 天</span>
              </div>
              <div className="script-export-head">
                <div className="script-export-day">第 {item.day_number} 天内容策划</div>
                <h1 className="script-export-title">{item.title_direction}</h1>
                <p className="script-export-subtitle">用于客户预览的完整脚本长图，包含标题策略、开头钩子、分镜节奏与发布信息。</p>
              </div>

              <div className="script-export-hero-grid">
                <div className="script-export-metric">
                  <div className="script-export-metric-label">建议时长</div>
                  <div className="script-export-metric-value">{script.estimated_duration?.trim() || '按分镜节奏执行'}</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">分镜数量</div>
                  <div className="script-export-metric-value">{script.storyboard?.length || 0} 个场景</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">标题备选</div>
                  <div className="script-export-metric-value">{(script.title_options || []).filter(Boolean).length || 0} 条</div>
                </div>
                <div className="script-export-metric">
                  <div className="script-export-metric-label">适用阶段</div>
                  <div className="script-export-metric-value">客户确认版</div>
                </div>
              </div>

              <div className="script-export-main">
                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">01</div>
                    <div>
                      <div className="script-export-card-label">标题备选</div>
                      <div className="script-export-section-subtitle">先看传播入口，优先筛出最有点击欲望的一版标题。</div>
                    </div>
                  </div>
                  <div className="script-export-list">
                    {((script.title_options || []).filter(Boolean).length ? (script.title_options || []).filter(Boolean) : ['待补充标题']).map((title, titleIndex) => (
                      <div key={`title-${titleIndex}`} className="script-export-list-item">
                        {title}
                      </div>
                    ))}
                  </div>
                </section>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">02</div>
                    <div>
                      <div className="script-export-card-label">黄金3秒开头</div>
                      <div className="script-export-section-subtitle">第一句就要抓人，避免平铺直叙地自我介绍。</div>
                    </div>
                  </div>
                  <div className="script-export-copy">{script.hook_script?.trim() || '待补充开头钩子'}</div>
                </section>

                <div className="script-export-grid">
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">03</div>
                      <div>
                        <div className="script-export-card-label">建议时长</div>
                        <div className="script-export-section-subtitle">方便客户快速判断拍摄密度。</div>
                      </div>
                    </div>
                    <div className="script-export-copy is-compact">{script.estimated_duration?.trim() || '按分镜节奏执行'}</div>
                  </section>
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">04</div>
                      <div>
                        <div className="script-export-card-label">完整口播思路</div>
                        <div className="script-export-section-subtitle">整体表达主线，帮助客户先抓核心感觉。</div>
                      </div>
                    </div>
                    <div className="script-export-copy is-compact">
                      {script.full_narration?.trim() || '以分镜中的台词内容为主线推进'}
                    </div>
                  </section>
                </div>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">05</div>
                    <div>
                      <div className="script-export-card-label">分镜脚本</div>
                      <div className="script-export-section-subtitle">逐镜头拆清楚画面、台词和拍摄动作，方便直接进入执行。</div>
                    </div>
                  </div>
                  <div className="script-export-scenes">
                    {(script.storyboard?.length ? script.storyboard : [{
                      scene: 1,
                      duration: '',
                      visual: '待补充分镜画面',
                      script: '待补充分镜台词',
                      camera: '待补充拍摄方式',
                    }]).map((scene, index) => (
                      <section key={`scene-${scene.scene}-${index}`} className="script-export-scene-card">
                        <div className="script-export-scene-head">
                          <span className="script-export-scene-badge">Scene {scene.scene}</span>
                          <span className="script-export-scene-duration">{scene.duration || '时长待定'}</span>
                        </div>
                        <div className="script-export-scene-body">
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">画面</div>
                            <div className="script-export-scene-value">{scene.visual}</div>
                          </div>
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">台词</div>
                            <div className="script-export-scene-value">{scene.script}</div>
                          </div>
                          <div className="script-export-scene-row">
                            <div className="script-export-scene-label">拍摄</div>
                            <div className="script-export-scene-value">{scene.camera}</div>
                          </div>
                        </div>
                      </section>
                    ))}
                  </div>
                </section>

                <section className="script-export-card">
                  <div className="script-export-section-head">
                    <div className="script-export-section-index">06</div>
                    <div>
                      <div className="script-export-card-label">发布文案</div>
                      <div className="script-export-section-subtitle">给客户直接看发布层表达，不只是拍摄层脚本。</div>
                    </div>
                  </div>
                  <div className="script-export-copy">{script.caption_template?.trim() || '待补充发布文案'}</div>
                </section>

                <div className="script-export-grid">
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">07</div>
                      <div>
                        <div className="script-export-card-label">话题标签</div>
                        <div className="script-export-section-subtitle">补足发布动作，方便直接带走使用。</div>
                      </div>
                    </div>
                    <div className="script-export-tags">
                      {((script.hashtag_suggestions || []).filter(Boolean).length ? (script.hashtag_suggestions || []).filter(Boolean) : ['待补充标签']).map((tag, tagIndex) => (
                        <span key={`tag-${tagIndex}`} className="script-export-tag">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </section>
                  <section className="script-export-card">
                    <div className="script-export-section-head is-compact">
                      <div className="script-export-section-index">08</div>
                      <div>
                        <div className="script-export-card-label">拍摄提醒</div>
                        <div className="script-export-section-subtitle">把执行注意点提前说透，减少反复确认。</div>
                      </div>
                    </div>
                    <div className="script-export-list is-compact">
                      {((script.filming_tips || []).filter(Boolean).length ? (script.filming_tips || []).filter(Boolean) : ['按分镜顺序执行，注意节奏和停顿']).map((tip, tipIndex) => (
                        <div key={`tip-${tipIndex}`} className="script-export-list-item is-compact">
                          {tip}
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              </div>

              <div className="script-export-footer">
                <span className="script-export-footer-mark">Douyin Manager</span>
                <span className="script-export-footer-text">此长图用于客户确认脚本方向，不替代现场拍摄微调。</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
