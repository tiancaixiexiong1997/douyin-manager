/**
 * API 客户端封装
 * 统一管理所有后端接口调用
 */
import axios from 'axios';

const rawApiOrigin = String(import.meta.env.VITE_API_URL || '').trim();
const normalizedApiOrigin = rawApiOrigin.replace(/\/+$/, '').replace(/\/api$/, '');
export const BASE_URL = normalizedApiOrigin;
const API_BASE = BASE_URL ? `${BASE_URL}/api` : '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

let refreshPromise: Promise<void> | null = null;

const ensureRefreshed = async () => {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE}/auth/refresh`, null, {
        timeout: 60000,
        withCredentials: true,
      })
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }
  await refreshPromise;
};

// ==========================================
// 视频脚本提取复刻 API
// ==========================================

export interface ExtractionCreateRequest {
  source_video_url: string;
  user_prompt?: string;
  plan_id?: string | null;
}

export interface ExtractionDraftPayload {
  source_video_url: string;
  user_prompt?: string;
  plan_id?: string | null;
}

export interface ExtractionDraftResponse {
  source_video_url: string;
  user_prompt: string;
  plan_id?: string | null;
  updated_at?: string | null;
}

export type ExtractionStatus = 'pending' | 'analyzing' | 'generating' | 'completed' | 'failed';

export interface ExtractionResponse {
  id: string;
  source_video_url: string;
  user_prompt: string;
  plan_id?: string | null;

  parsed_video_url?: string;
  title?: string;
  description?: string;
  cover_url?: string;

  highlight_analysis?: {
    core_theme: string;
    success_structure: string;
    hook_mechanism: string;
    copywriting_style: string;
    visual_rhythm: string;
    audio_emotion: string;
  };

  user_guide_summary?: {
    theme_direction: string;
    target_audience: string;
    core_tension: string;
  };

  generated_script?: {
    title_suggestion: string;
    opening_hook: string;
    middle_body: string;
    ending_call: string;
    storyboard: Array<{
      scene: number;
      duration: string;
      visual: string;
      script: string;
      camera: string;
      emotion_beat: string;
    }>;
    optimization_tips: string[];
  };

  status: ExtractionStatus;
  error_message?: string;
  retry_count?: number;
  max_retries?: number;

  created_at: string;
  updated_at: string;
}

export interface ExtractionListResponse {
  id: string;
  source_video_url: string;
  title?: string;
  cover_url?: string;
  status: ExtractionStatus;
  retry_count?: number;
  max_retries?: number;
  created_at: string;
}

export const scriptApi = {
  createExtraction: async (data: ExtractionCreateRequest): Promise<ExtractionResponse> => {
    const res = await api.post('/script/extract', data);
    return res as unknown as ExtractionResponse;
  },

  getDraft: async (): Promise<ExtractionDraftResponse> => {
    const res = await api.get('/script/draft');
    return res as unknown as ExtractionDraftResponse;
  },

  saveDraft: async (data: ExtractionDraftPayload): Promise<ExtractionDraftResponse> => {
    const res = await api.put('/script/draft', data);
    return res as unknown as ExtractionDraftResponse;
  },

  getExtraction: async (id: string): Promise<ExtractionResponse> => {
    const res = await api.get(`/script/${id}`);
    return res as unknown as ExtractionResponse;
  },

  listExtractions: async (skip = 0, limit = 20): Promise<ExtractionListResponse[]> => {
    const res = await api.get('/script', { params: { skip, limit } });
    return res as unknown as ExtractionListResponse[];
  },

  deleteExtraction: async (id: string): Promise<{ message: string }> => {
    const res = await api.delete(`/script/${id}`);
    return res as unknown as { message: string };
  }
};

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    const status = err.response?.status as number | undefined;
    const original = err.config as ({ _retry?: boolean; url?: string } & Record<string, unknown>) | undefined;
    const requestUrl = String(original?.url || '');
    const isAuthPath = requestUrl.includes('/auth/login') || requestUrl.includes('/auth/refresh') || requestUrl.includes('/auth/logout');

    if (status === 401 && original && !original._retry && !isAuthPath) {
      original._retry = true;
      try {
        await ensureRefreshed();
        return api(original);
      } catch {
        // 刷新失败，走统一错误提示
      }
    }

    const detail = err.response?.data?.detail;
    const rawMessage = typeof detail === 'string' ? detail : (err.message || '请求失败');
    let msg = rawMessage;
    if (status === 401 && !isAuthPath) msg = '登录已过期，请重新登录';
    else if (status === 403) msg = '你没有权限执行这个操作';
    else if (status === 404) msg = '请求的数据不存在或已被删除';
    else if (status && status >= 500) msg = `服务暂时不可用（${status}），请稍后重试`;
    return Promise.reject(new Error(msg));
  }
);

// ============ 博主 IP 库接口 ============

export interface Blogger {
  id: string;
  platform: string;
  blogger_id: string;
  nickname: string;
  avatar_url?: string;
  signature?: string;
  representative_video_url?: string;
  follower_count: number;
  following_count: number;
  total_like_count: number;
  video_count: number;
  analysis_report?: BloggerAnalysisReport;
  is_analyzed: boolean;
  incremental_enabled?: boolean;
  last_collected_at?: string | null;
  last_collected_published_at?: string | null;
  videos?: BloggerVideo[];
  created_at: string;
  updated_at: string;
}

export interface BloggerAnalysisReport {
  ip_positioning?: {
    core_identity: string;
    target_audience: string;
    content_niche: string;
    personality_tags: string[];
  };
  content_strategy?: {
    dominant_content_type: string;
    posting_style: string;
    hook_patterns: string;
    topic_pillars: string[];
  };
  filming_signature?: {
    visual_style: string;
    editing_signature: string;
    production_level: string;
    unique_techniques?: string;
  };
  copywriting_dna?: {
    tone_of_voice: string;
    typical_hook?: string;
    typical_hooks?: string[];
    cta_patterns: string;
    interaction_style?: string;
  };
  growth_insights?: {
    success_formula: string;
    audience_pain_points: string;
    differentiation?: string;
  };
  reference_value?: {
    learnable_elements: string[];
    avoid_elements?: string[];
    inspiration_score: number;
  };
  viral_profile?: BloggerViralProfile;
  viral_profile_updated_at?: string;
}

export interface BloggerViralProfile {
  account_planning_logic?: string;
  why_it_went_viral?: string;
  content_playbook?: string[];
  risk_warnings?: string[];
  evidence_samples?: Array<{
      title?: string;
      reason?: string;
  }>;
  timeline_overview?: string;
  timeline_entries?: Array<{
    date?: string;
    title?: string;
    phase?: string;
    performance_signal?: string;
    topic_pattern?: string;
    post_fire_role?: string;
    why_it_mattered?: string;
  }>;
  post_fire_arrangement?: string;
  planning_takeaways?: string[];
  confidence_score?: number;
}

export interface VideoAnalysis {
  content_summary?: string;
  filming_style?: {
    shot_types: string;
    editing_pace: string;
    visual_style: string;
    special_techniques: string;
  };
  copywriting_style?: {
    hook_method: string;
    language_tone: string;
    structure: string;
    cta_style: string;
  };
  audio_style?: {
    bgm: string;
    sound_effects: string;
    voice_style: string;
    audio_pacing: string;
  };
  content_strategy?: {
    content_type: string;
    target_pain_points: string;
    engagement_tactics: string;
  };
  viral_factors?: string[];
}

export interface BloggerVideo {
  id: string;
  video_id: string;
  title?: string;
  cover_url?: string;
  video_url?: string;
  like_count: number;
  comment_count: number;
  duration: number;
  published_at?: string;
  ai_analysis?: VideoAnalysis;
  is_analyzed: boolean;
  created_at: string;
}

export interface AddBloggerRequest {
  url: string;
  representative_video_url?: string;
  sample_count?: number | null;  // null = 全部
  start_date?: string;
  end_date?: string;
  incremental_mode?: boolean;
}

export interface ReanalyzeBloggerRequest {
  sample_count?: number | null;  // null = 全部
  start_date?: string;
  end_date?: string;
  incremental_mode?: boolean;
}

export interface BloggerProgress {
  step: string;
  message: string;
}

export interface PagedListResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export interface ListQueryParams {
  skip?: number;
  limit?: number;
}

export interface BloggerListQueryParams extends ListQueryParams {
  keyword?: string;
  platform?: string;
}

export interface PlanningListQueryParams extends ListQueryParams {
  keyword?: string;
  status?: 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed' | 'in_progress';
}

export const bloggerApi = {
  /** 添加博主 */
  add: (data: AddBloggerRequest): Promise<Blogger> =>
    api.post('/bloggers', data),

  /** 获取博主列表 */
  list: (params?: BloggerListQueryParams): Promise<Blogger[]> =>
    api.get('/bloggers', { params }),

  /** 获取博主分页列表（含 total/has_more） */
  listPaged: (params?: BloggerListQueryParams): Promise<PagedListResponse<Blogger>> =>
    api.get('/bloggers', {
      params: { ...(params || {}), with_meta: true },
    }),

  /** 获取博主详情 */
  get: (id: string): Promise<Blogger> =>
    api.get(`/bloggers/${id}`),

  /** 删除博主 */
  remove: (id: string): Promise<void> =>
    api.delete(`/bloggers/${id}`),

  /** 重新采集并分析博主 */
  reanalyze: (id: string, data?: ReanalyzeBloggerRequest): Promise<void> =>
    api.post(`/bloggers/${id}/reanalyze`, data),

  /** 查询博主后台分析进度 */
  getProgress: (id: string): Promise<BloggerProgress> =>
    api.get(`/bloggers/${id}/progress`),

  /** 生成博主爆款归因报告 */
  generateViralProfile: (id: string): Promise<{ message: string; task_started?: boolean; task_enqueued?: boolean }> =>
    api.post(`/bloggers/${id}/generate-viral-profile`),

  /** 删除某个指定的视频记录及深度分析 */
  removeVideo: (bloggerId: string, videoId: string): Promise<{ message: string, is_rep_deleted: boolean }> =>
    api.delete(`/bloggers/${bloggerId}/videos/${videoId}`),

  /** 将视频设为代表作并触发深度析帧 */
  setRepresentative: (bloggerId: string, data: {
    video_url: string;
    video_id: string;
    title?: string;
    description?: string;
    cover_url?: string;
    like_count?: number;
    published_at?: string;
  }): Promise<{ message: string; task_started?: boolean; task_enqueued?: boolean }> =>
    api.post(`/bloggers/${bloggerId}/set-representative`, data),

  /** 通过鉴权代理下载博主视频二进制 */
  proxyDownload: (params: { url: string; filename?: string; video_id?: string }): Promise<Blob> =>
    api.get('/bloggers/proxy-download', { params, responseType: 'blob' }) as unknown as Promise<Blob>,
};

// ============ 策划项目接口 ============

export interface PlanningProject {
  id: string;
  client_name: string;
  industry: string;
  target_audience: string;
  unique_advantage?: string;
  ip_requirements: string;
  style_preference?: string;
  business_goal?: string;
  reference_blogger_ids?: string[];
  account_homepage_url?: string;
  account_nickname?: string;
  account_avatar_url?: string;
  account_signature?: string;
  account_follower_count?: number;
  account_video_count?: number;
  account_plan?: AccountPlan;
  content_calendar?: ContentCalendarItem[];
  status: 'draft' | 'strategy_generating' | 'strategy_completed' | 'calendar_generating' | 'completed' | 'in_progress';
  content_items?: ContentItem[];
  created_at: string;
  updated_at: string;
}

export interface AccountPlan {
  account_positioning?: {
    core_identity: string;
    target_audience_detail: string;
    content_pillars: Array<{ name: string; description: string; ratio: string }>;
    personality_tags: string[];
    bio_suggestion: string;
    differentiation?: string;
    user_value?: string;
    follow_reason?: string;
  };
  content_strategy?: {
    primary_format: string;
    posting_frequency: string;
    best_posting_times: string[];
    content_tone: string;
    stop_scroll_reason?: string;
    interaction_trigger?: string;
    hook_template?: string;
    cta_template?: string;
  };
  backup_topic_pool?: Array<{
    title_direction: string;
    content_type: string;
    content_pillar?: string | null;
    key_message?: string | null;
    tags?: string[];
    batch_shoot_group?: string | null;
    replacement_hint?: string | null;
  }>;
  calendar_generation_meta?: {
    blocked_count: number;
    backup_used_count: number;
    regeneration_count: number;
  };
  quality_notes?: string;
  performance_recap?: PerformanceRecap;
  next_topic_batch?: NextTopicBatch;
}

export interface PerformanceRecap {
  generated_at: string;
  overall_summary: string;
  winning_patterns: string[];
  optimization_focus: string[];
  risk_alerts: string[];
  next_actions: string[];
  next_topic_angles: string[];
}

export interface NextTopicBatchItem {
  title_direction: string;
  content_type: string;
  content_pillar?: string | null;
  hook_hint?: string | null;
  why_this_angle?: string | null;
  imported_content_item_id?: string | null;
  imported_day_number?: number | null;
  imported_at?: string | null;
}

export interface NextTopicBatch {
  generated_at: string;
  overall_strategy: string;
  items: NextTopicBatchItem[];
}

export interface ContentCalendarItem {
  day: number;
  title_direction: string;
  content_type: string;
  content_pillar?: string;
  key_message?: string;
  tags?: string[];
  priority?: string;
  content_role?: string;
  is_main_validation?: boolean;
  production_mode?: string;
  production_type?: string;
  production_reason?: string;
  is_batch_shootable?: boolean;
  batch_shoot_group?: string;
  replacement_hint?: string;
}

export interface ContentItem {
  id: string;
  day_number: number;
  title_direction: string;
  content_type?: string;
  tags?: string[];
  full_script?: VideoScript;
  is_script_generated: boolean;
}

export interface ContentItemUpdateRequest {
  title_direction?: string;
  content_type?: string;
  tags?: string[];
  full_script?: VideoScript;
}

export interface VideoScript {
  title_options?: string[];
  hook_script?: string;
  storyboard?: Array<{
    scene: number;
    duration: string;
    visual: string;
    script: string;
    camera: string;
  }>;
  full_narration?: string;
  caption_template?: string;
  hashtag_suggestions?: string[];
  filming_tips?: string[];
  estimated_duration?: string;
}

export interface ContentPerformance {
  id: string;
  project_id: string;
  content_item_id?: string | null;
  title: string;
  platform: string;
  publish_date?: string | null;
  video_url?: string | null;
  views: number;
  bounce_2s_rate?: number | null;
  completion_5s_rate?: number | null;
  completion_rate?: number | null;
  likes: number;
  comments: number;
  shares: number;
  conversions: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContentPerformanceCreateRequest {
  content_item_id?: string | null;
  title: string;
  platform?: string;
  publish_date?: string | null;
  video_url?: string | null;
  views?: number;
  bounce_2s_rate?: number | null;
  completion_5s_rate?: number | null;
  completion_rate?: number | null;
  likes?: number;
  comments?: number;
  shares?: number;
  conversions?: number;
  notes?: string | null;
}

export interface ContentPerformanceUpdateRequest {
  content_item_id?: string | null;
  title?: string;
  platform?: string;
  publish_date?: string | null;
  video_url?: string | null;
  views?: number;
  bounce_2s_rate?: number | null;
  completion_5s_rate?: number | null;
  completion_rate?: number | null;
  likes?: number;
  comments?: number;
  shares?: number;
  conversions?: number;
  notes?: string | null;
}

export interface ContentPerformanceInsight {
  title: string;
  body: string;
  tone: 'good' | 'warn' | 'neutral';
}

export interface ContentPerformanceSummary {
  total_items: number;
  planned_content_count: number;
  coverage_rate?: number | null;
  total_views: number;
  avg_bounce_2s_rate?: number | null;
  avg_completion_5s_rate?: number | null;
  avg_completion_rate?: number | null;
  avg_engagement_rate?: number | null;
  avg_conversion_rate?: number | null;
  total_likes: number;
  total_comments: number;
  total_shares: number;
  total_conversions: number;
  top_items: ContentPerformance[];
  best_view_item?: ContentPerformance | null;
  best_completion_item?: ContentPerformance | null;
  best_engagement_item?: ContentPerformance | null;
  best_conversion_item?: ContentPerformance | null;
  insights: ContentPerformanceInsight[];
}

export interface CreatePlanningRequest {
  client_name: string;
  industry: string;
  target_audience: string;
  unique_advantage?: string;
  ip_requirements: string;
  style_preference?: string;
  business_goal?: string;
  reference_blogger_ids: string[];
  account_homepage_url?: string;
}

export interface PlanningIntakeDraft {
  client_name: string;
  industry: string;
  target_audience: string;
  unique_advantage: string;
  ip_requirements: string;
  style_preference: string;
  business_goal: string;
  publishing_rhythm: string;
  time_windows: string;
  goal_target: string;
  iteration_rule: string;
}

export interface PlanningIntakeChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface PlanningIntakeAssistantRequest {
  user_message: string;
  draft: PlanningIntakeDraft;
  chat_history: PlanningIntakeChatMessage[];
  auto_complete?: boolean;
  mode?: 'normal' | 'fast';
}

export interface PlanningIntakeAssistantResponse {
  assistant_reply: string;
  draft: PlanningIntakeDraft;
  missing_fields: string[];
  inferred_fields: string[];
  ready_for_reference: boolean;
  ready_for_generate: boolean;
  confirmation_summary?: string | null;
  suggested_questions: string[];
}

export interface UpdatePlanningRequest {
  client_name?: string;
  industry?: string;
  target_audience?: string;
  unique_advantage?: string;
  ip_requirements?: string;
  style_preference?: string;
  business_goal?: string;
  account_plan?: AccountPlan;
}

export const planningApi = {
  /** 互动问诊助手（创建策划前） */
  intakeAssistant: (data: PlanningIntakeAssistantRequest): Promise<PlanningIntakeAssistantResponse> =>
    api.post('/planning/intake-assistant', data),

  /** 创建策划项目 */
  create: (data: CreatePlanningRequest): Promise<PlanningProject> =>
    api.post('/planning', data),

  /** 生成账号定位方案 */
  generateStrategy: (id: string): Promise<{ message: string; status: string }> =>
    api.post(`/planning/${id}/generate-strategy`),

  /** 获取项目列表 */
  list: (params?: PlanningListQueryParams): Promise<PlanningProject[]> =>
    api.get('/planning', { params }),

  /** 获取项目分页列表（含 total/has_more） */
  listPaged: (params?: PlanningListQueryParams): Promise<PagedListResponse<PlanningProject>> =>
    api.get('/planning', {
      params: { ...(params || {}), with_meta: true },
    }),

  /** 获取项目详情 */
  get: (id: string): Promise<PlanningProject> =>
    api.get(`/planning/${id}`),

  /** 删除策划项目（后台任务同时取消） */
  remove: (id: string): Promise<void> =>
    api.delete(`/planning/${id}`),

  /** 重新生成草稿状态的策划项目 */
  retry: (id: string): Promise<{ message: string; status: string }> =>
    api.post(`/planning/${id}/retry`),

  /** 单独重新生成 30 天内容日历 */
  regenerateCalendar: (id: string): Promise<{ message: string; status: string }> =>
    api.post(`/planning/${id}/regenerate-calendar`),

  /** 为内容条目生成脚本 */
  generateScript: (contentItemId: string, bloggerIds?: string[]): Promise<{ script: VideoScript }> =>
    api.post('/planning/script/generate', {
      content_item_id: contentItemId,
      reference_blogger_ids: bloggerIds || [],
    }),

  /** 更新内容条目（标题/类型/脚本） */
  updateContentItem: (itemId: string, data: ContentItemUpdateRequest): Promise<ContentItem> =>
    api.patch(`/planning/content-items/${itemId}`, data),

  /** 补填/更新账号主页地址（自动抓取头像昵称简介） */
  updateHomepage: (id: string, url: string): Promise<PlanningProject> =>
    api.patch(`/planning/${id}/homepage`, { account_homepage_url: url }),

  /** 编辑策划项目基本信息 */
  update: (id: string, data: UpdatePlanningRequest): Promise<PlanningProject> =>
    api.patch(`/planning/${id}`, data),

  /** 获取发布回流记录 */
  listPerformance: (projectId: string): Promise<ContentPerformance[]> =>
    api.get(`/planning/${projectId}/performance`),

  /** 新增发布回流记录 */
  createPerformance: (projectId: string, data: ContentPerformanceCreateRequest): Promise<ContentPerformance> =>
    api.post(`/planning/${projectId}/performance`, data),

  /** 更新发布回流记录 */
  updatePerformance: (projectId: string, performanceId: string, data: ContentPerformanceUpdateRequest): Promise<ContentPerformance> =>
    api.patch(`/planning/${projectId}/performance/${performanceId}`, data),

  /** 删除发布回流记录 */
  removePerformance: (projectId: string, performanceId: string): Promise<{ message: string }> =>
    api.delete(`/planning/${projectId}/performance/${performanceId}`),

  /** 发布回流汇总 */
  getPerformanceSummary: (projectId: string): Promise<ContentPerformanceSummary> =>
    api.get(`/planning/${projectId}/performance-summary`),

  /** 生成 AI 发布复盘 */
  generatePerformanceRecap: (projectId: string): Promise<PerformanceRecap> =>
    api.post(`/planning/${projectId}/performance-recap`),

  /** 生成下一批10条选题 */
  generateNextTopicBatch: (projectId: string): Promise<NextTopicBatch> =>
    api.post(`/planning/${projectId}/next-topic-batch`),

  /** 将选题批次中的某条加入内容日历 */
  importNextTopicBatchItem: (projectId: string, itemIndex: number): Promise<ContentItem> =>
    api.post(`/planning/${projectId}/next-topic-batch/${itemIndex}/import`),
};

export interface SettingsData {
  AI_API_KEY?: string;
  AI_BASE_URL?: string;
  AI_MODEL?: string;
  GLOBAL_AI_FACT_RULES?: string;
  GLOBAL_AI_WRITING_RULES?: string;
  BLOGGER_REPORT_PROMPT?: string;
  ACCOUNT_PLAN_PROMPT?: string;
  CONTENT_CALENDAR_PROMPT?: string;
  VIDEO_SCRIPT_PROMPT?: string;
  SCRIPT_REMAKE_PROMPT?: string;
  DOUYIN_COOKIE?: string;
}

export interface SettingsPayload {
  settings: SettingsData;
  defaults: SettingsData;
}

export interface CookieExtractorStatus {
  token: string;
  login_url: string;
  extension_path: string;
  cookie_length: number;
  last_synced_at?: string | null;
  last_service?: string | null;
  last_message?: string | null;
}

export interface CookieExtractorRotateResponse {
  token: string;
  message: string;
}

export const settingApi = {
  /** 获取系统设置 */
  getSettings: (): Promise<SettingsPayload> =>
    api.get('/settings').then((res) => res as unknown as SettingsPayload),

  /** 保存系统设置 */
  saveSettings: (data: SettingsData): Promise<{ message: string }> =>
    api.put('/settings', { settings: data }),

  /** 获取 Cookie 提取助手状态 */
  getCookieExtractorStatus: (): Promise<CookieExtractorStatus> =>
    api.get('/settings/cookie-extractor'),

  /** 重置 Cookie 提取助手 token */
  rotateCookieExtractorToken: (): Promise<CookieExtractorRotateResponse> =>
    api.post('/settings/cookie-extractor/rotate-token'),
};

// ============ 下载工具接口 ============

export interface LoginRequest {
  username: string;
  password: string;
}

export type UserRole = 'admin' | 'member' | 'viewer';

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  username: string;
  role: UserRole;
}

export interface CurrentUserResponse {
  id: string;
  username: string;
  role: UserRole;
}

export interface UserItem {
  id: string;
  username: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  items: UserItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: UserRole;
  is_active?: boolean;
}

export interface UserUpdateRequest {
  role?: UserRole;
  is_active?: boolean;
}

export interface OperationLogItem {
  id: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  actor: string;
  detail?: string | null;
  extra?: Record<string, unknown> | null;
  created_at: string;
}

export interface OperationLogListQueryParams {
  skip?: number;
  limit?: number;
  action?: string;
  actor?: string;
}

export interface ScheduleEntry {
  id: string;
  schedule_date: string;
  title: string;
  content_type?: string | null;
  notes?: string | null;
  done: boolean;
  created_by_user_id?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleListQueryParams {
  start_date?: string;
  end_date?: string;
  skip?: number;
  limit?: number;
}

export interface ScheduleCreateRequest {
  schedule_date: string;
  title: string;
  content_type?: string | null;
  notes?: string | null;
  done?: boolean;
}

export interface ScheduleUpdateRequest {
  schedule_date?: string;
  title?: string;
  content_type?: string | null;
  notes?: string | null;
  done?: boolean;
}

export const authApi = {
  login: (data: LoginRequest): Promise<LoginResponse> =>
    api.post('/auth/login', data),
  refresh: (): Promise<LoginResponse> =>
    api.post('/auth/refresh'),
  logout: (): Promise<{ message: string }> =>
    api.post('/auth/logout'),
  me: (): Promise<CurrentUserResponse> =>
    api.get('/auth/me'),
};

export const userApi = {
  list: (params?: {
    skip?: number;
    limit?: number;
    keyword?: string;
    role?: UserRole;
    is_active?: boolean;
    sort_by?: 'created_at' | 'username' | 'role' | 'is_active';
    sort_order?: 'asc' | 'desc';
  }): Promise<UserListResponse> =>
    api.get('/users', { params }),
  create: (data: UserCreateRequest): Promise<UserItem> =>
    api.post('/users', data),
  update: (id: string, data: UserUpdateRequest): Promise<UserItem> =>
    api.patch(`/users/${id}`, data),
  resetPassword: (id: string, password: string): Promise<{ message: string }> =>
    api.post(`/users/${id}/reset-password`, { password }),
  remove: (id: string): Promise<{ message: string }> =>
    api.delete(`/users/${id}`),
  batchStatus: (userIds: string[], isActive: boolean): Promise<{ message: string; updated: number }> =>
    api.patch('/users/batch-status', { user_ids: userIds, is_active: isActive }),
  batchDelete: (userIds: string[]): Promise<{ message: string; deleted: number; skipped: number }> =>
    api.post('/users/batch-delete', { user_ids: userIds }),
};

export const logApi = {
  list: (params?: OperationLogListQueryParams): Promise<OperationLogItem[]> =>
    api.get('/logs', { params }),
  listPaged: (params?: OperationLogListQueryParams): Promise<PagedListResponse<OperationLogItem>> =>
    api.get('/logs', { params: { ...(params || {}), with_meta: true } }),
};

export const scheduleApi = {
  list: (params?: ScheduleListQueryParams): Promise<ScheduleEntry[]> =>
    api.get('/schedules', { params }),
  create: (data: ScheduleCreateRequest): Promise<ScheduleEntry> =>
    api.post('/schedules', data),
  update: (id: string, data: ScheduleUpdateRequest): Promise<ScheduleEntry> =>
    api.patch(`/schedules/${id}`, data),
  remove: (id: string): Promise<{ message: string }> =>
    api.delete(`/schedules/${id}`),
};

export interface TaskCenterItem {
  id: string;
  task_key: string;
  task_type: string;
  title: string;
  entity_type: string;
  entity_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress_step?: string | null;
  message?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskCenterListResponse {
  items: TaskCenterItem[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
  summary: Record<string, number>;
}

export interface TaskCenterQueryParams {
  skip?: number;
  limit?: number;
  status?: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  task_type?: string;
  entity_type?: string;
}

export const taskApi = {
  list: (params?: TaskCenterQueryParams): Promise<TaskCenterListResponse> =>
    api.get('/tasks', { params }),
};

export interface PromptScene {
  scene_key: string;
  name: string;
  setting_key: string;
}

export interface PromptVersion {
  id: string;
  scene_key: string;
  version_label: string;
  template_text: string;
  is_active: boolean;
  source_setting_key?: string | null;
  created_by?: string | null;
  created_at: string;
}

export interface PromptExperiment {
  id: string;
  scene_key: string;
  name: string;
  version_a_id: string;
  version_b_id: string;
  traffic_ratio_a: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PromptRun {
  id: string;
  scene_key: string;
  entity_type?: string | null;
  entity_id?: string | null;
  status: string;
  prompt_version_id?: string | null;
  ab_experiment_id?: string | null;
  ab_branch?: string | null;
  score?: number | null;
  feedback?: string | null;
  output_preview?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptCompareResult {
  version_a: {
    version_id: string;
    runs: number;
    avg_score?: number | null;
    success_rate: number;
  };
  version_b: {
    version_id: string;
    runs: number;
    avg_score?: number | null;
    success_rate: number;
  };
}

export const aiPromptApi = {
  scenes: (): Promise<PromptScene[]> =>
    api.get('/ai-prompts/scenes'),
  listVersions: (scene_key: string): Promise<PromptVersion[]> =>
    api.get('/ai-prompts/versions', { params: { scene_key } }),
  createVersion: (data: {
    scene_key: string;
    version_label: string;
    template_text: string;
    source_setting_key?: string;
    is_active?: boolean;
  }): Promise<PromptVersion> =>
    api.post('/ai-prompts/versions', data),
  activateVersion: (versionId: string): Promise<PromptVersion> =>
    api.patch(`/ai-prompts/versions/${versionId}/activate`),
  listExperiments: (scene_key: string): Promise<PromptExperiment[]> =>
    api.get('/ai-prompts/experiments', { params: { scene_key } }),
  createExperiment: (data: {
    scene_key: string;
    name: string;
    version_a_id: string;
    version_b_id: string;
    traffic_ratio_a: number;
    is_active?: boolean;
  }): Promise<PromptExperiment> =>
    api.post('/ai-prompts/experiments', data),
  updateExperiment: (id: string, data: {
    name?: string;
    traffic_ratio_a?: number;
    is_active?: boolean;
  }): Promise<PromptExperiment> =>
    api.patch(`/ai-prompts/experiments/${id}`, data),
  listRuns: (params?: { scene_key?: string; prompt_version_id?: string; skip?: number; limit?: number }): Promise<PromptRun[]> =>
    api.get('/ai-prompts/runs', { params }),
  scoreRun: (runId: string, payload: { score: number; feedback?: string }): Promise<PromptRun> =>
    api.post(`/ai-prompts/runs/${runId}/score`, payload),
  compare: (version_a_id: string, version_b_id: string): Promise<PromptCompareResult> =>
    api.get('/ai-prompts/compare', { params: { version_a_id, version_b_id } }),
};

export interface ParseVideoResponse {
  video_id: string;
  title: string;
  cover_url: string;
  video_url: string;
  platform?: string;
  published_at?: string | null;
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  share_count?: number;
}

export const downloadApi = {
  /** 解析视频短链接获取直链 */
  parse: (url: string): Promise<ParseVideoResponse> =>
    api.post('/download/parse', null, { params: { url } }),

  /** 通过鉴权代理下载视频二进制 */
  proxyDownload: (params: { url: string; filename?: string; video_id?: string }): Promise<Blob> =>
    api.get('/download/proxy-download', { params, responseType: 'blob' }) as unknown as Promise<Blob>,
};

export default api;
