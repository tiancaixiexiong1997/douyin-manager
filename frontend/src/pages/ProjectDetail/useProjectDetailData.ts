import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  bloggerApi,
  planningApi,
  type ContentCalendarItem,
  type PlanningProject,
} from '../../api/client';
import {
  inferProjectStage,
  type CalendarDisplayItem,
} from './projectDetailShared';

export function useProjectDetailData(projectId?: string) {
  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => planningApi.get(projectId!),
    enabled: Boolean(projectId),
  });

  const { data: bloggers = [] } = useQuery({
    queryKey: ['bloggers'],
    queryFn: () => bloggerApi.list(),
  });

  const { data: performanceList = [] } = useQuery({
    queryKey: ['project-performance', projectId],
    queryFn: () => planningApi.listPerformance(projectId!),
    enabled: Boolean(projectId),
  });

  const { data: performanceSummary } = useQuery({
    queryKey: ['project-performance-summary', projectId],
    queryFn: () => planningApi.getPerformanceSummary(projectId!),
    enabled: Boolean(projectId),
  });

  const plan = project?.account_plan;
  const currentStage = project ? inferProjectStage(project) : 'draft';
  const storeGrowthPlan = plan?.store_growth_plan;
  const positioning = plan?.account_positioning;
  const strategy = plan?.content_strategy;
  const hasStrategy = Boolean(storeGrowthPlan || positioning || strategy);
  const hasCalendar = Boolean((project?.content_calendar || []).length > 0 || (project?.content_items || []).length > 0);
  const performanceRecap = plan?.performance_recap;
  const nextTopicBatch = plan?.next_topic_batch;

  const calendarDisplayItems = useMemo<CalendarDisplayItem[]>(() => {
    const calendarMetaByDay = new Map<number, ContentCalendarItem>(
      (project?.content_calendar || [])
        .filter((item): item is ContentCalendarItem => Boolean(item && typeof item.day === 'number'))
        .map((item) => [item.day, item]),
    );

    return (project?.content_items || [])
      .map((item) => ({
        ...item,
        calendarMeta: calendarMetaByDay.get(item.day_number) || null,
      }))
      .sort((a, b) => a.day_number - b.day_number);
  }, [project?.content_calendar, project?.content_items]);

  const referenceNames = useMemo(() => {
    const bloggerNameMap = new Map(bloggers.map((blogger) => [blogger.id, blogger.nickname]));
    return (project?.reference_blogger_ids || [])
      .map((bloggerId) => bloggerNameMap.get(bloggerId))
      .filter((name): name is string => Boolean(name));
  }, [bloggers, project?.reference_blogger_ids]);

  const referenceScopeItems = useMemo(
    () => [
      `增长策划会参考 ${referenceNames.join('、')} 的切入角度、受众表达方式和内容支柱拆法，但会优先贴合你当前门店的行业、目标受众和商业目标。`,
      '30 天内容日历会参考这些 IP 里更稳定的选题方向、内容结构和更新节奏，用来辅助规划每天拍什么，不会直接照搬某一条内容。',
      '后续生成单条脚本时，也会继续参考这些 IP 的开头节奏、表达习惯和镜头组织方式，但脚本会按你当前项目的增长策略重新写。',
      '如果后面你更换或减少参考 IP，重新生成策划和日历后，下面这套方案也会跟着变化。',
    ],
    [referenceNames],
  );

  return {
    project: project as PlanningProject | undefined,
    isLoading,
    plan,
    storeGrowthPlan,
    positioning,
    strategy,
    currentStage,
    hasStrategy,
    hasCalendar,
    performanceList,
    performanceSummary,
    performanceRecap,
    nextTopicBatch,
    calendarDisplayItems,
    referenceNames,
    referenceScopeItems,
  };
}
