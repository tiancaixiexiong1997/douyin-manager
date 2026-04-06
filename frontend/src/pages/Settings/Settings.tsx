import React, { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingApi, type SettingsData } from '../../api/client';
import { Save, Settings as SettingsIcon, Link2, Key, Cpu, User, FileText, LayoutTemplate, PenTool, Bot, Copy, QrCode, RotateCcw, RefreshCw } from 'lucide-react';
import { formatBackendDateTime } from '../../utils/datetime';
import { notifyError, notifySuccess } from '../../utils/notify';
import './Settings.css';

export default function Settings() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<SettingsData>({});
  const [activeTab, setActiveTab] = useState('basic');
  const isCrawlerTab = activeTab === 'crawler';

  const { data, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingApi.getSettings(),
  });

  const {
    data: extractorStatus,
    refetch: refetchExtractorStatus,
    isFetching: isExtractorStatusFetching,
  } = useQuery({
    queryKey: ['cookie-extractor-status'],
    queryFn: () => settingApi.getCookieExtractorStatus(),
    enabled: isCrawlerTab,
  });

  const formData = useMemo(
    () => ({ ...(data?.settings || {}), ...draft }),
    [data, draft]
  );

  const defaultSettings = data?.defaults || {};

  const webhookUrl = extractorStatus?.token
    ? `${window.location.origin}/api/settings/cookie-extractor/webhook?token=${extractorStatus.token}`
    : '';

  const mutation = useMutation({
    mutationFn: (newSettings: SettingsData) => settingApi.saveSettings(newSettings),
    onSuccess: () => {
      notifySuccess('设置保存成功');
      setDraft({});
      queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (err: unknown) => {
      const message = err instanceof Error ? err.message : '未知错误';
      notifyError(`保存失败：${message}`);
    }
  });

  const rotateExtractorTokenMutation = useMutation({
    mutationFn: () => settingApi.rotateCookieExtractorToken(),
    onSuccess: (result) => {
      notifySuccess(result.message);
      queryClient.invalidateQueries({ queryKey: ['cookie-extractor-status'] });
    },
    onError: (err: unknown) => {
      notifyError(err instanceof Error ? err.message : '重置 Cookie 提取 token 失败');
    },
  });

  if (isLoading || !data) {
    return <div className="settings-page"><div className="loading">加载设置中...</div></div>;
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setDraft((prev) => ({ ...prev, [name]: value }));
  };

  const handleResetPrompt = (key: keyof SettingsData, label: string) => {
    const defaultValue = defaultSettings[key];
    if (typeof defaultValue !== 'string') {
      notifyError(`未找到${label}的默认提示词`);
      return;
    }
    setDraft((prev) => ({ ...prev, [key]: defaultValue }));
    notifySuccess(`${label}已恢复为默认提示词`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (Object.keys(draft).length > 0) {
      mutation.mutate(draft);
    }
  };

  const handleCopyWebhookUrl = async () => {
    if (!webhookUrl) {
      notifyError('Webhook 地址尚未生成');
      return;
    }
    try {
      await navigator.clipboard.writeText(webhookUrl);
      notifySuccess('Webhook 地址已复制');
    } catch {
      notifyError('复制失败，请手动复制');
    }
  };

  const handleOpenDouyinLogin = () => {
    const loginUrl = extractorStatus?.login_url || 'https://www.douyin.com/';
    window.open(loginUrl, '_blank', 'noopener,noreferrer');
  };

  const formatExtractorTime = (value?: string | null) => {
    if (!value) return '尚未同步';
    return formatBackendDateTime(value, {}, '尚未同步');
  };

  const tabs = [
    { id: 'basic', label: '基础配置', icon: SettingsIcon, group: '通用' },
    { id: 'crawler', label: '爬虫与认证', icon: Key, group: '通用' },
    { id: 'prompt_global', label: '全局写作规则', icon: Bot, group: '系统提示词' },
    { id: 'prompt_blogger', label: '博主 IP 分析', icon: User, group: '系统提示词' },
    { id: 'prompt_plan', label: '账号定位方案', icon: LayoutTemplate, group: '系统提示词' },
    { id: 'prompt_calendar', label: '30天内容日历', icon: LayoutTemplate, group: '系统提示词' },
    { id: 'prompt_script', label: '单条视频脚本', icon: FileText, group: '系统提示词' },
    { id: 'prompt_remake', label: '视频拆解复刻', icon: PenTool, group: '系统提示词' },
  ];

  const getActiveTabInfo = () => tabs.find(t => t.id === activeTab);
  const ActiveTabIcon = getActiveTabInfo()?.icon || SettingsIcon;

  const renderPromptActions = (key: keyof SettingsData, label: string) => (
    <div className="prompt-actions">
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        onClick={() => handleResetPrompt(key, label)}
      >
        <RotateCcw size={14} /> 恢复默认提示词
      </button>
    </div>
  );

  return (
    <div className="settings-page">
      <section className="settings-hero">
        <div className="settings-hero-pill"><SettingsIcon size={13} /> System Config</div>
        <h1>系统设置中心</h1>
        <p>统一管理模型参数、抓取认证和全链路提示词，保存后立即作用于整个系统。</p>
      </section>

      <div className="settings-container">
        <div className="settings-sidebar card">
          <div className="settings-menu">
            <div className="settings-menu-group">通用</div>
            <button 
              className={`settings-menu-item ${activeTab === 'basic' ? 'active' : ''}`}
              onClick={() => setActiveTab('basic')}
            >
              <Cpu size={16} /> 基础大模型配置
            </button>
            <button 
              className={`settings-menu-item ${activeTab === 'crawler' ? 'active' : ''}`}
              onClick={() => setActiveTab('crawler')}
            >
              <Key size={16} /> 爬虫与认证设置
            </button>
            <div className="settings-menu-group" style={{ marginTop: '16px' }}>系统提示词 (Prompts)</div>
            {tabs.filter(t => t.group === '系统提示词').map(tab => {
              const Icon = tab.icon;
              return (
                <button 
                  key={tab.id}
                  className={`settings-menu-item ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <Icon size={16} /> {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="settings-content card">
          <form onSubmit={handleSubmit}>
            <div className="settings-content-header">
              <h2 className="flex items-center gap-2">
                <div className="tab-icon-wrap"><ActiveTabIcon size={18} className="text-primary-500" /></div>
                {getActiveTabInfo()?.label}
              </h2>
              <button type="submit" className="btn btn-primary btn-sm" disabled={mutation.isPending}>
                <Save size={14} /> {mutation.isPending ? '保存中...' : '保存当前设置'}
              </button>
            </div>

            <div className="settings-scroll-area">
              {activeTab === 'basic' && (
                <div className="animate-fade-in settings-form-grid">
                  <div className="form-group">
                    <label><Key size={16} className="text-primary-500"/> 大模型 API Key</label>
                    <input 
                      type="password" 
                      name="AI_API_KEY"
                      value={formData.AI_API_KEY ?? ''}
                      onChange={handleChange}
                      placeholder="sk-..."
                    />
                    <span className="help-text">全系统统一使用这一套大模型配置，账号策划、日历、脚本、视频解析都会走它。</span>
                  </div>

                  <div className="form-group">
                    <label><Link2 size={16} className="text-primary-500"/> 大模型 Base URL</label>
                    <input 
                      type="text" 
                      name="AI_BASE_URL"
                      value={formData.AI_BASE_URL ?? ''}
                      onChange={handleChange}
                    />
                    <span className="help-text">代理接口地址或官方接口地址，通常需带上 /v1 后缀。</span>
                  </div>

                  <div className="form-group">
                    <label><Bot size={16} className="text-primary-500"/> 大模型名称</label>
                    <input 
                      type="text" 
                      name="AI_MODEL"
                      value={formData.AI_MODEL ?? ''}
                      onChange={handleChange}
                    />
                    <span className="help-text">所有任务统一走这一模型，不再区分文本模型和多模态模型。</span>
                  </div>

                </div>
              )}

              {activeTab === 'crawler' && (
                <div className="animate-fade-in settings-form-grid">
                  <div className="form-group">
                    <label><Key size={16} className="text-primary-500"/> Douyin Cookie</label>
                    <textarea 
                      name="DOUYIN_COOKIE"
                      value={formData.DOUYIN_COOKIE || ''} 
                      onChange={handleChange}
                      className="settings-cookie-textarea"
                      placeholder="复制并在上方粘贴您的抖音 Web 网页端 Cookie... (如: sessionid=xxx; msToken=...)"
                    />
                    <span className="help-text">
                      此 Cookie 用于底层抓取及代理下载无水印视频。如果失效将导致解析/下载时直接返回 403 或空数据。
                    </span>
                  </div>

                  <div className="cookie-extractor-card">
                    <div className="cookie-extractor-header">
                      <div>
                        <h3><QrCode size={18} /> Cookie 提取助手</h3>
                        <p>通过浏览器扩展接收抖音登录后的 Cookie，并自动回写到当前系统。</p>
                      </div>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => refetchExtractorStatus()}
                        disabled={isExtractorStatusFetching}
                      >
                        <RefreshCw size={14} /> {isExtractorStatusFetching ? '刷新中...' : '刷新状态'}
                      </button>
                    </div>

                    <div className="cookie-extractor-stats">
                      <div className="cookie-extractor-stat">
                        <span>当前 Cookie 长度</span>
                        <strong>{extractorStatus?.cookie_length ?? 0}</strong>
                      </div>
                      <div className="cookie-extractor-stat">
                        <span>最近同步时间</span>
                        <strong>{formatExtractorTime(extractorStatus?.last_synced_at)}</strong>
                      </div>
                      <div className="cookie-extractor-stat">
                        <span>最近同步来源</span>
                        <strong>{extractorStatus?.last_service || '未连接'}</strong>
                      </div>
                    </div>

                    <div className="cookie-extractor-field">
                      <label>Webhook 地址</label>
                      <div className="cookie-extractor-input-row">
                        <input
                          type="text"
                          value={webhookUrl}
                          readOnly
                          placeholder="进入本页后自动生成"
                        />
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={handleCopyWebhookUrl}
                          disabled={!webhookUrl}
                        >
                          <Copy size={14} /> 复制
                        </button>
                      </div>
                      <span className="help-text">
                        将这个地址填到浏览器扩展里，扩展会把扫码登录后的 Douyin Cookie 自动回传到系统。
                      </span>
                    </div>

                    <div className="cookie-extractor-actions">
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={handleOpenDouyinLogin}
                      >
                        <QrCode size={14} /> 打开抖音扫码登录
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => rotateExtractorTokenMutation.mutate()}
                        disabled={rotateExtractorTokenMutation.isPending}
                      >
                        <RotateCcw size={14} /> {rotateExtractorTokenMutation.isPending ? '重置中...' : '重置 Token'}
                      </button>
                    </div>

                    <div className="cookie-extractor-guide">
                      <div className="cookie-extractor-guide-title">使用步骤</div>
                      <ol>
                        <li>在 Chrome 加载扩展目录：<code>{extractorStatus?.extension_path || 'backend/douyin_api/chrome-cookie-sniffer'}</code></li>
                        <li>打开扩展弹窗，将上方 Webhook 地址粘贴进去并保存。</li>
                        <li>点击“打开抖音扫码登录”，在新标签页完成抖音扫码登录。</li>
                        <li>登录后刷新一次抖音页面或浏览任意页面，扩展会自动抓取并回写 Cookie。</li>
                      </ol>
                    </div>

                    {extractorStatus?.last_message && (
                      <div className="cookie-extractor-message">
                        最近反馈：{extractorStatus.last_message}
                      </div>
                    )}
                  </div>
                </div>
              )}


              {activeTab === 'prompt_global' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="form-group">
                    <label className="prompt-label"><Bot size={16} className="text-primary-500"/> 全局事实底线 <span className="label-badge">Global</span></label>
                    {renderPromptActions('GLOBAL_AI_FACT_RULES', '全局事实底线')}
                    <textarea
                      name="GLOBAL_AI_FACT_RULES"
                      value={formData.GLOBAL_AI_FACT_RULES ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>作用范围：</strong>
                      所有 AI 场景统一生效，主要约束不编造、信息不足直说、少空话、严格遵守输出格式。
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="prompt-label"><PenTool size={16} className="text-primary-500"/> 全局去 AI 味规则 <span className="label-badge">Global</span></label>
                    {renderPromptActions('GLOBAL_AI_WRITING_RULES', '全局去 AI 味规则')}
                    <textarea
                      name="GLOBAL_AI_WRITING_RULES"
                      value={formData.GLOBAL_AI_WRITING_RULES ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>作用范围：</strong>
                      仅对用户会直接看到的文案类场景生效，比如账号策划、脚本、复盘、下一批选题、互动问诊，用来压住导师腔、反问句和营销黑话。
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompt_blogger' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="ai-card" style={{ marginBottom: 16 }}>
                    <div className="ai-card-title"><Bot size={16} /> 当前提示词还会叠加全局规则</div>
                    <div className="text-sm text-secondary">
                      这里写的是场景专属约束；系统运行时会先注入“全局事实底线”，部分文案场景还会额外注入“全局去 AI 味规则”。
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="prompt-label"><User size={16} className="text-primary-500"/> 博主 IP 分析提示词 <span className="label-badge">Prompt</span></label>
                    {renderPromptActions('BLOGGER_REPORT_PROMPT', '博主 IP 分析提示词')}
                    <textarea 
                      name="BLOGGER_REPORT_PROMPT"
                      value={formData.BLOGGER_REPORT_PROMPT ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>可用变量：</strong>
                      <code>{'{nickname}'}</code> <code>{'{platform}'}</code> <code>{'{follower_count}'}</code> <code>{'{signature}'}</code> <code>{'{video_count}'}</code> <code>{'{text_data_json}'}</code> <code>{'{analyses_json}'}</code>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompt_plan' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="form-group">
                    <label className="prompt-label"><LayoutTemplate size={16} className="text-primary-500"/> 账号定位方案提示词 <span className="label-badge">Prompt</span></label>
                    {renderPromptActions('ACCOUNT_PLAN_PROMPT', '账号定位方案提示词')}
                    <textarea 
                      name="ACCOUNT_PLAN_PROMPT"
                      value={formData.ACCOUNT_PLAN_PROMPT ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>可用变量：</strong>
                      <code>{'{client_name}'}</code> <code>{'{industry}'}</code> <code>{'{target_audience}'}</code> <code>{'{unique_advantage}'}</code> <code>{'{ip_requirements}'}</code> <code>{'{style_preference}'}</code> <code>{'{business_goal}'}</code> <code>{'{blogger_count}'}</code> <code>{'{bloggers_text}'}</code>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompt_calendar' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="form-group">
                    <label className="prompt-label"><LayoutTemplate size={16} className="text-primary-500"/> 30天内容日历提示词 <span className="label-badge">Prompt</span></label>
                    {renderPromptActions('CONTENT_CALENDAR_PROMPT', '30天内容日历提示词')}
                    <textarea 
                      name="CONTENT_CALENDAR_PROMPT"
                      value={formData.CONTENT_CALENDAR_PROMPT ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>可用变量：</strong>
                      <code>{'{client_name}'}</code> <code>{'{core_identity}'}</code> <code>{'{target_audience_detail}'}</code> <code>{'{personality_tags}'}</code> <code>{'{differentiation}'}</code> <code>{'{content_tone}'}</code> <code>{'{content_pillars}'}</code> <code>{'{performance_recap_summary}'}</code> <code>{'{winning_patterns}'}</code> <code>{'{optimization_focus}'}</code> <code>{'{next_topic_angles}'}</code>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompt_script' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="form-group">
                    <label className="prompt-label"><FileText size={16} className="text-primary-500"/> 单条视频脚本生成提示词 <span className="label-badge">Prompt</span></label>
                    {renderPromptActions('VIDEO_SCRIPT_PROMPT', '单条视频脚本生成提示词')}
                    <textarea 
                      name="VIDEO_SCRIPT_PROMPT"
                      value={formData.VIDEO_SCRIPT_PROMPT ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>可用变量：</strong>
                      <code>{'{title_direction}'}</code> <code>{'{content_type}'}</code> <code>{'{key_message}'}</code> <code>{'{core_identity}'}</code> <code>{'{content_tone}'}</code> <code>{'{target_audience_detail}'}</code>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'prompt_remake' && (
                <div className="animate-fade-in prompt-full-height">
                  <div className="form-group">
                    <label className="prompt-label"><PenTool size={16} className="text-primary-500"/> 视频脚本拆解复刻提示词 <span className="label-badge">Prompt</span></label>
                    {renderPromptActions('SCRIPT_REMAKE_PROMPT', '视频脚本拆解复刻提示词')}
                    <textarea 
                      name="SCRIPT_REMAKE_PROMPT"
                      value={formData.SCRIPT_REMAKE_PROMPT ?? ''}
                      onChange={handleChange}
                      className="prompt-textarea"
                    />
                    <div className="prompt-variables">
                      <strong>可用变量：</strong>
                      <code>{'{title}'}</code> <code>{'{description}'}</code> <code>{'{user_prompt}'}</code>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
