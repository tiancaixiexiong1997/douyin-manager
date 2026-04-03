import type {
  ContentCalendarItem,
  ContentItem,
  PlanningProject,
  TaskCenterItem,
  TaskCenterListResponse,
} from '../../api/client';

export type CalendarDisplayItem = ContentItem & { calendarMeta?: ContentCalendarItem | null };

export type PendingCalendarRegeneration = {
  dayNumbers: number[];
  snapshotsByDay: Record<number, CalendarDisplayItem>;
};

type PlanningTaskContext = {
  planning_state?: string;
  regeneration_mode?: 'initial' | 'full' | 'partial';
  regenerate_day_numbers?: number[];
  calendar_snapshots?: Array<{
    id: string;
    day_number: number;
    title_direction: string;
    content_type?: string | null;
    tags?: string[] | null;
    is_script_generated?: boolean;
    calendar_meta?: ContentCalendarItem | null;
  }>;
};

export type ProjectStage =
  | 'draft'
  | 'strategy_generating'
  | 'strategy_completed'
  | 'calendar_generating'
  | 'completed';

export function hasMeaningfulStoreGrowthPlan(storeGrowthPlan?: unknown): boolean {
  if (!storeGrowthPlan || typeof storeGrowthPlan !== 'object') return false;
  const plan = storeGrowthPlan as Record<string, unknown>;
  const storePositioning = (plan.store_positioning || {}) as Record<string, unknown>;
  const decisionTriggers = (plan.decision_triggers || {}) as Record<string, unknown>;
  const contentModel = (plan.content_model || {}) as Record<string, unknown>;
  const onCameraStrategy = (plan.on_camera_strategy || {}) as Record<string, unknown>;
  const conversionPath = (plan.conversion_path || {}) as Record<string, unknown>;
  const executionRules = (plan.execution_rules || {}) as Record<string, unknown>;

  const visitDecisionFactors = Array.isArray(decisionTriggers.visit_decision_factors)
    ? decisionTriggers.visit_decision_factors.filter(Boolean)
    : [];
  const contentPillars = Array.isArray(contentModel.content_pillars)
    ? contentModel.content_pillars.filter((item) => item && typeof item === 'object' && (item as Record<string, unknown>).name)
    : [];
  const trafficHooks = Array.isArray(contentModel.traffic_hooks)
    ? contentModel.traffic_hooks.filter(Boolean)
    : [];
  const recommendedRoles = Array.isArray(onCameraStrategy.recommended_roles)
    ? onCameraStrategy.recommended_roles.filter((item) => item && typeof item === 'object' && (item as Record<string, unknown>).role)
    : [];

  return Boolean(
    storePositioning.market_position &&
    visitDecisionFactors.length >= 1 &&
    contentPillars.length >= 1 &&
    trafficHooks.length >= 1 &&
    recommendedRoles.length >= 1 &&
    conversionPath.traffic_to_trust &&
    executionRules.posting_frequency
  );
}

export function inferProjectStage(project: {
  status: string;
  account_plan?: {
    store_growth_plan?: unknown;
    account_positioning?: unknown;
    content_strategy?: unknown;
    calendar_generation_meta?: unknown;
  } | null;
}): ProjectStage {
  const hasStoreStrategy = hasMeaningfulStoreGrowthPlan(project.account_plan?.store_growth_plan);
  const hasStrategy = Boolean(hasStoreStrategy || project.account_plan?.account_positioning || project.account_plan?.content_strategy);
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

export function isPendingTask(task?: TaskCenterItem | null): boolean {
  return task?.status === 'queued' || task?.status === 'running';
}

function parsePlanningTaskContext(task?: TaskCenterItem | null): PlanningTaskContext | null {
  const context = task?.context;
  if (!context || typeof context !== 'object') return null;
  return context as PlanningTaskContext;
}

export function buildPendingCalendarRegeneration(task?: TaskCenterItem | null): PendingCalendarRegeneration | null {
  if (!isPendingTask(task)) return null;
  const context = parsePlanningTaskContext(task);
  if (!context || context.planning_state !== 'calendar_regenerating') return null;

  const dayNumbers = Array.from(
    new Set(
      (context.regenerate_day_numbers || []).filter(
        (value): value is number => Number.isInteger(value) && value >= 1 && value <= 30,
      ),
    ),
  ).sort((a, b) => a - b);
  if (dayNumbers.length === 0) return null;

  const snapshotsByDay: Record<number, CalendarDisplayItem> = {};
  for (const snapshot of context.calendar_snapshots || []) {
    if (!snapshot || !Number.isInteger(snapshot.day_number)) continue;
    snapshotsByDay[snapshot.day_number] = {
      id: snapshot.id,
      day_number: snapshot.day_number,
      title_direction: snapshot.title_direction,
      content_type: snapshot.content_type || undefined,
      tags: snapshot.tags || undefined,
      is_script_generated: Boolean(snapshot.is_script_generated),
      full_script: undefined,
      calendarMeta: snapshot.calendar_meta || null,
    };
  }

  return { dayNumbers, snapshotsByDay };
}

export function upsertOptimisticTask(
  current: TaskCenterListResponse | undefined,
  task: TaskCenterItem,
): TaskCenterListResponse {
  const items = [task, ...(current?.items || []).filter((item) => item.task_key !== task.task_key)];
  return {
    items,
    total: Math.max(current?.total || 0, items.length),
    skip: current?.skip || 0,
    limit: current?.limit || 20,
    has_more: false,
    summary: current?.summary || {},
  };
}

export type ProjectDetailData = PlanningProject;
