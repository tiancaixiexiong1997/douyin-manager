import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  planningApi,
  type PlanningProject,
  type TaskCenterItem,
  type TaskCenterListResponse,
} from '../../api/client';
import {
  upsertOptimisticTask,
  type CalendarDisplayItem,
} from './projectDetailShared';

type UseProjectDetailActionsArgs = {
  projectId?: string;
  project?: PlanningProject;
  hasStrategy: boolean;
  hasCalendar: boolean;
  calendarDisplayItems: CalendarDisplayItem[];
};

export function useProjectDetailActions({
  projectId,
  project,
  hasStrategy,
  hasCalendar,
  calendarDisplayItems,
}: UseProjectDetailActionsArgs) {
  const qc = useQueryClient();

  const refreshProject = () => {
    qc.invalidateQueries({ queryKey: ['project', projectId] });
    qc.invalidateQueries({ queryKey: ['project-planning-tasks', projectId] });
  };

  const refreshPerformance = () => {
    qc.invalidateQueries({ queryKey: ['project-performance', projectId] });
    qc.invalidateQueries({ queryKey: ['project-performance-summary', projectId] });
  };

  const generateStrategyMutation = useMutation({
    mutationFn: () => planningApi.generateStrategy(projectId!),
    onMutate: async () => {
      const optimisticTask: TaskCenterItem = {
        id: `optimistic-strategy-${projectId}`,
        task_key: `planning:${projectId}:generate-strategy`,
        task_type: 'planning_generate',
        title: `生成定位：${project?.client_name || projectId}`,
        entity_type: 'planning_project',
        entity_id: projectId!,
        status: 'queued',
        progress_step: 'queued',
        message: '定位生成任务已提交',
        context: {
          planning_state: 'strategy_regenerating',
          has_existing_strategy: hasStrategy,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const previousTaskPage = qc.getQueryData<TaskCenterListResponse>([
        'project-planning-tasks',
        projectId,
      ]);
      qc.setQueryData<TaskCenterListResponse>(['project-planning-tasks', projectId], (current) =>
        upsertOptimisticTask(current, optimisticTask),
      );
      return { previousTaskPage };
    },
    onSuccess: refreshProject,
    onError: (_error, _variables, context) => {
      qc.setQueryData(['project-planning-tasks', projectId], context?.previousTaskPage);
    },
  });

  const regenerateCalendarMutation = useMutation({
    mutationFn: (dayNumbers: number[]) =>
      planningApi.regenerateCalendar(projectId!, { regenerate_day_numbers: dayNumbers }),
    onMutate: async (dayNumbers) => {
      const fallbackDayNumbers =
        calendarDisplayItems.length > 0
          ? calendarDisplayItems.map((item) => item.day_number)
          : (project?.content_calendar || []).map((item) => item.day);
      const isPartialRegeneration = dayNumbers.length > 0 && hasCalendar;
      const targetDays = (dayNumbers.length > 0 ? dayNumbers : fallbackDayNumbers)
        .filter((dayNumber, index, source) => source.indexOf(dayNumber) === index)
        .sort((a, b) => a - b);
      const snapshots = calendarDisplayItems
        .filter((item) => targetDays.includes(item.day_number))
        .map((item) => ({
          id: item.id,
          day_number: item.day_number,
          title_direction: item.title_direction,
          content_type: item.content_type || null,
          tags: item.tags || [],
          is_script_generated: item.is_script_generated,
          calendar_meta:
            item.calendarMeta ||
            (project?.content_calendar || []).find(
              (calendarItem) => calendarItem.day === item.day_number,
            ) ||
            null,
        }));
      const optimisticTask: TaskCenterItem = {
        id: `optimistic-calendar-${projectId}`,
        task_key: `planning:${projectId}:calendar`,
        task_type: 'planning_calendar',
        title: `${hasCalendar ? '重生成日历' : '生成日历'}：${project?.client_name || projectId}`,
        entity_type: 'planning_project',
        entity_id: projectId!,
        status: 'queued',
        progress_step: 'queued',
        message: isPartialRegeneration
          ? `已提交局部重生成任务，将重写 Day ${targetDays.join(', ')}`
          : '30天日历生成任务已提交',
        context: {
          planning_state: 'calendar_regenerating',
          regeneration_mode: isPartialRegeneration ? 'partial' : hasCalendar ? 'full' : 'initial',
          regenerate_day_numbers: targetDays,
          calendar_snapshots: snapshots,
        },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      const previousTaskPage = qc.getQueryData<TaskCenterListResponse>([
        'project-planning-tasks',
        projectId,
      ]);
      qc.setQueryData<TaskCenterListResponse>(['project-planning-tasks', projectId], (current) =>
        upsertOptimisticTask(current, optimisticTask),
      );
      return { previousTaskPage };
    },
    onSuccess: refreshProject,
    onError: (_error, _variables, context) => {
      qc.setQueryData(['project-planning-tasks', projectId], context?.previousTaskPage);
    },
  });

  const generatePerformanceRecapMutation = useMutation({
    mutationFn: () => planningApi.generatePerformanceRecap(projectId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const generateNextTopicBatchMutation = useMutation({
    mutationFn: () => planningApi.generateNextTopicBatch(projectId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const importNextTopicBatchItemMutation = useMutation({
    mutationFn: ({ itemIndex }: { itemIndex: number }) =>
      planningApi.importNextTopicBatchItem(projectId!, itemIndex),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const removePerformanceMutation = useMutation({
    mutationFn: (performanceId: string) => planningApi.removePerformance(projectId!, performanceId),
    onSuccess: refreshPerformance,
  });

  return {
    generateStrategyMutation,
    regenerateCalendarMutation,
    generatePerformanceRecapMutation,
    generateNextTopicBatchMutation,
    importNextTopicBatchItemMutation,
    removePerformanceMutation,
    refreshProject,
    refreshPerformance,
  };
}
