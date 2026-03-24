import { useEffect, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { taskApi, type PlanningProject, type TaskCenterItem, type TaskCenterListResponse } from '../../api/client';
import { toBackendTimestamp } from '../../utils/datetime';
import {
  buildPendingCalendarRegeneration,
  type CalendarDisplayItem,
  isPendingTask,
  type ProjectStage,
} from './projectDetailShared';

type UsePlanningTaskStateArgs = {
  projectId?: string;
  project?: PlanningProject;
  currentStage: ProjectStage;
  hasStrategy: boolean;
  calendarDisplayItems: CalendarDisplayItem[];
};

export function usePlanningTaskState({
  projectId,
  project,
  currentStage,
  hasStrategy,
  calendarDisplayItems,
}: UsePlanningTaskStateArgs) {
  const qc = useQueryClient();
  const lastTaskRefreshSignatureRef = useRef<string | null>(null);

  const projectContentItemIdSet = useMemo(
    () => new Set((project?.content_items || []).map((item) => item.id)),
    [project?.content_items],
  );

  const { data: scriptTaskPage } = useQuery({
    queryKey: ['content-script-tasks', projectId],
    queryFn: () =>
      taskApi.list({
        entity_type: 'content_item',
        task_type: 'planning_script_generate',
        limit: 200,
      }),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const page = query.state.data as TaskCenterListResponse | undefined;
      if (!page) return false;
      const hasPendingTasks = page.items.some(
        (task) => isPendingTask(task) && projectContentItemIdSet.has(task.entity_id),
      );
      return hasPendingTasks ? 3000 : false;
    },
  });

  const { data: projectTaskPage } = useQuery({
    queryKey: ['project-planning-tasks', projectId],
    queryFn: () =>
      taskApi.list({
        entity_type: 'planning_project',
        entity_id: projectId!,
        limit: 50,
      }),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const page = query.state.data as TaskCenterListResponse | undefined;
      if (!page) return false;
      return page.items.some((task) => isPendingTask(task)) ? 3000 : false;
    },
  });

  const scriptTaskMap = useMemo(() => {
    const map = new Map<string, TaskCenterItem>();
    const tasks = scriptTaskPage?.items || [];
    for (const task of tasks) {
      const prev = map.get(task.entity_id);
      if (!prev || toBackendTimestamp(task.updated_at) >= toBackendTimestamp(prev.updated_at)) {
        map.set(task.entity_id, task);
      }
    }
    return map;
  }, [scriptTaskPage]);

  const latestPlanningTaskByType = useMemo(() => {
    const map = new Map<string, TaskCenterItem>();
    for (const task of projectTaskPage?.items || []) {
      const previous = map.get(task.task_type);
      if (!previous || toBackendTimestamp(task.updated_at) >= toBackendTimestamp(previous.updated_at)) {
        map.set(task.task_type, task);
      }
    }
    return map;
  }, [projectTaskPage]);

  const projectScriptTasks = useMemo(
    () => (scriptTaskPage?.items || []).filter((task) => projectContentItemIdSet.has(task.entity_id)),
    [projectContentItemIdSet, scriptTaskPage],
  );

  const latestStrategyTask = latestPlanningTaskByType.get('planning_generate') || null;
  const latestCalendarTask = latestPlanningTaskByType.get('planning_calendar') || null;
  const pendingCalendarRegeneration = useMemo(
    () => buildPendingCalendarRegeneration(latestCalendarTask),
    [latestCalendarTask],
  );

  const visibleCalendarItems = useMemo(() => {
    if (!pendingCalendarRegeneration) return calendarDisplayItems;
    const currentByDay = new Map(calendarDisplayItems.map((item) => [item.day_number, item]));
    const mergedItems = [...calendarDisplayItems];
    for (const dayNumber of pendingCalendarRegeneration.dayNumbers) {
      if (currentByDay.has(dayNumber)) continue;
      const snapshot = pendingCalendarRegeneration.snapshotsByDay[dayNumber];
      if (snapshot) mergedItems.push(snapshot);
    }
    return mergedItems.sort((a, b) => a.day_number - b.day_number);
  }, [calendarDisplayItems, pendingCalendarRegeneration]);

  const pendingRegenerationDaySet = useMemo(
    () => new Set(pendingCalendarRegeneration?.dayNumbers || []),
    [pendingCalendarRegeneration],
  );

  const isStrategyRegenerating = Boolean(
    hasStrategy && (currentStage === 'strategy_generating' || isPendingTask(latestStrategyTask)),
  );

  const taskDrivenRefreshSignature = useMemo(
    () =>
      JSON.stringify({
        strategy: latestStrategyTask
          ? [latestStrategyTask.status, latestStrategyTask.progress_step, latestStrategyTask.updated_at]
          : null,
        calendar: latestCalendarTask
          ? [latestCalendarTask.status, latestCalendarTask.progress_step, latestCalendarTask.updated_at]
          : null,
        scripts: projectScriptTasks
          .map((task) => `${task.entity_id}:${task.status}:${task.progress_step || ''}:${task.updated_at}`)
          .sort(),
      }),
    [latestCalendarTask, latestStrategyTask, projectScriptTasks],
  );

  useEffect(() => {
    lastTaskRefreshSignatureRef.current = null;
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !project) return;
    if (!taskDrivenRefreshSignature) return;
    if (lastTaskRefreshSignatureRef.current === null) {
      lastTaskRefreshSignatureRef.current = taskDrivenRefreshSignature;
      return;
    }
    if (lastTaskRefreshSignatureRef.current === taskDrivenRefreshSignature) return;
    lastTaskRefreshSignatureRef.current = taskDrivenRefreshSignature;
    qc.invalidateQueries({ queryKey: ['project', projectId] });
  }, [projectId, project, qc, taskDrivenRefreshSignature]);

  return {
    latestStrategyTask,
    latestCalendarTask,
    scriptTaskMap,
    visibleCalendarItems,
    pendingRegenerationDaySet,
    isStrategyRegenerating,
  };
}
