import logging

from app.models.database import TaskStatus
from app.models.db_session import AsyncSessionLocal
from app.repository.blogger_repo import blogger_repository
from app.repository.planning_repo import planning_repository
from app.repository.task_center_repo import task_center_repo
from app.services.ai_analysis_service import ai_analysis_service
from app.services.cancellation import cancellation_registry
from app.services.planning_calendar_guardrails import regenerate_selected_calendar_days
from app.services.planning_calendar_utils import (
    build_calendar_task_context,
    build_strategy_task_context,
    has_meaningful_strategy_result,
    normalize_content_calendar,
    normalize_content_type,
)

logger = logging.getLogger(__name__)


async def generate_plan_background(
    project_id: str,
    client_data: dict,
    blogger_ids: list,
    task_key: str | None = None,
    fallback_status: str | None = None,
):
    """后台任务：生成账号定位和内容日历（关键步骤均检查取消）"""
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"planning:{project_id}:generate"
        project = await planning_repository.get_by_id(db, project_id)
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="planning_generate",
            title=f"生成策划：{project.client_name if project else project_id}",
            entity_type="planning_project",
            entity_id=project_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message="开始生成账号策划",
            context=build_strategy_task_context(project)
            if project
            else {
                "planning_state": "strategy_regenerating",
                "has_existing_strategy": False,
            },
        )
        await db.commit()
        try:
            if cancellation_registry.is_cancelled(project_id):
                logger.info("项目 %s 已被取消，跳过生成", project_id)
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="任务已取消",
                )
                await db.commit()
                return

            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="collect_reference",
                message="收集参考博主分析数据",
            )
            await db.commit()

            reference_bloggers = []
            for bid in blogger_ids:
                blogger = await blogger_repository.get_by_id(db, bid)
                if blogger:
                    report = blogger.analysis_report if isinstance(blogger.analysis_report, dict) else {}
                    reference_bloggers.append(
                        {
                            "nickname": blogger.nickname,
                            "analysis_report": report,
                            "viral_profile": report.get("viral_profile"),
                        }
                    )

            logger.info("开始为项目 %s 生成策划方案...", project_id)
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_generate",
                message="AI 正在生成账号定位方案",
            )
            await db.commit()
            result = await ai_analysis_service.generate_account_plan(
                client_info=client_data,
                reference_bloggers=reference_bloggers,
                run_context={"entity_type": "planning_project", "entity_id": project_id},
                db=db,
            )

            if result.get("error"):
                logger.error("项目 %s AI 分析返回 error: %s", project_id, result["error"])
                raise Exception(result["error"])

            logger.info("项目 %s AI 结果包含字段: %s", project_id, list(result.keys()))
            if "raw_analysis" in result:
                logger.warning(
                    "由于解析失败，AI 直接返回了 raw_analysis (前500字符): %s",
                    result["raw_analysis"][:500],
                )

            if cancellation_registry.is_cancelled(project_id):
                logger.info("项目 %s 在 AI 完成后被取消，不写入数据库", project_id)
                return

            account_positioning = result.get("account_positioning", {})
            content_strategy = result.get("content_strategy", {})

            if not has_meaningful_strategy_result(account_positioning, content_strategy):
                logger.error("项目 %s AI 返回空定位结果，拒绝覆盖原有内容", project_id)
                raise ValueError("AI 返回的定位结果为空，未覆盖原有内容")

            account_plan = {
                "account_positioning": account_positioning,
                "content_strategy": content_strategy,
            }

            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入账号定位结果",
            )
            await planning_repository.delete_content_items_by_project(db, project_id)
            await planning_repository.update_strategy_result(db, project_id, account_plan)

            await db.commit()
            logger.info("项目 %s 定位方案生成完成", project_id)
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message="账号定位方案生成完成，可继续生成 30 天日历",
            )
            await db.commit()

        except Exception as exc:
            logger.error("项目 %s 定位生成失败: %s", project_id, exc, exc_info=True)
            project = await planning_repository.get_by_id(db, project_id)
            if project:
                project.status = fallback_status or "draft"
                await db.commit()
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="账号定位方案生成失败",
                error_message=str(exc),
            )
            await db.commit()
        finally:
            cancellation_registry.clear(project_id)


async def generate_calendar_only_background(
    project_id: str,
    client_data: dict,
    account_plan: dict,
    task_key: str | None = None,
    regenerate_day_numbers: list[int] | None = None,
):
    """后台任务：仅生成 30 天内容日历"""
    async with AsyncSessionLocal() as db:
        resolved_task_key = task_key or f"planning:{project_id}:calendar"
        project = await planning_repository.get_by_id(db, project_id)
        selected_days = sorted({day for day in (regenerate_day_numbers or []) if isinstance(day, int) and 1 <= day <= 30})
        has_existing_calendar = bool(project and (project.content_calendar or project.content_items))
        is_partial_regenerate = has_existing_calendar and bool(selected_days)
        await task_center_repo.upsert_task(
            db,
            task_key=resolved_task_key,
            task_type="planning_calendar",
            title=f"{'局部重生成日历' if is_partial_regenerate else ('重生成日历' if has_existing_calendar else '生成日历')}：{project.client_name if project else project_id}",
            entity_type="planning_project",
            entity_id=project_id,
            status=TaskStatus.RUNNING.value,
            progress_step="start",
            message=(
                f"开始重生成 Day {', '.join(str(day) for day in selected_days)}"
                if is_partial_regenerate
                else "开始生成30天内容日历"
            ),
            context=build_calendar_task_context(project, selected_days)
            if project
            else {
                "planning_state": "calendar_regenerating",
                "regeneration_mode": "partial" if selected_days else "initial",
                "regenerate_day_numbers": selected_days,
                "calendar_snapshots": [],
            },
        )
        await db.commit()
        try:
            if cancellation_registry.is_cancelled(project_id):
                logger.info("日历重构: 项目 %s 已被取消，跳过生成", project_id)
                await task_center_repo.update_status(
                    db,
                    resolved_task_key,
                    status=TaskStatus.CANCELLED.value,
                    progress_step="cancelled",
                    message="日历重生成任务已取消",
                )
                await db.commit()
                return

            logger.info("日历重构: 开始为项目 %s 生成 30 天内容日历...", project_id)
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="ai_generate",
                message=(
                    f"AI 正在重写 Day {', '.join(str(day) for day in selected_days)}"
                    if is_partial_regenerate
                    else "AI 正在结合最新复盘建议生成新的 30 天日历"
                    if isinstance(account_plan, dict) and isinstance(account_plan.get("performance_recap"), dict)
                    else "AI 正在生成新的 30 天日历"
                ),
            )
            await db.commit()
            if is_partial_regenerate:
                content_calendar, calendar_meta, quality_notes = await regenerate_selected_calendar_days(
                    project=project,
                    client_data=client_data,
                    account_plan=account_plan,
                    regenerate_days=selected_days,
                    project_id=project_id,
                    db=db,
                )
            else:
                result = await ai_analysis_service.generate_content_calendar(
                    client_info=client_data,
                    account_plan=account_plan,
                    run_context={"entity_type": "planning_project", "entity_id": project_id},
                    db=db,
                )

                if result.get("error"):
                    logger.error("日历重构: 项目 %s AI 分析返回 error: %s", project_id, result["error"])
                    raise Exception(result["error"])

                if cancellation_registry.is_cancelled(project_id):
                    return

                content_calendar = normalize_content_calendar(result.get("content_calendar", []))
                if len(content_calendar) != 30:
                    raise ValueError(f"内容日历输出数量异常，应为30条，实际 {len(content_calendar)} 条")
                calendar_meta = {
                    "blocked_count": 0,
                    "backup_used_count": 0,
                    "regeneration_count": 0,
                }
                quality_notes = ""

            if cancellation_registry.is_cancelled(project_id):
                return
            persisted_account_plan = dict(account_plan or {})
            persisted_account_plan["backup_topic_pool"] = []
            persisted_account_plan["calendar_generation_meta"] = calendar_meta
            persisted_account_plan["quality_notes"] = quality_notes

            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.RUNNING.value,
                progress_step="persist",
                message="正在写入重生成结果",
            )
            await planning_repository.update_plan_result(db, project_id, persisted_account_plan, content_calendar)

            if is_partial_regenerate:
                await planning_repository.delete_content_items_by_days(db, project_id, selected_days)
                content_items_to_create = [item for item in content_calendar if item.get("day") in selected_days]
            else:
                await planning_repository.delete_content_items_by_project(db, project_id)
                content_items_to_create = content_calendar

            for item_data in content_items_to_create:
                await planning_repository.add_content_item(
                    db,
                    {
                        "project_id": project_id,
                        "day_number": item_data.get("day", 1),
                        "title_direction": item_data.get("title_direction", ""),
                        "content_type": normalize_content_type(item_data.get("content_type")),
                        "tags": item_data.get("tags", []),
                    },
                )

            await db.commit()
            logger.info("日历重构: 项目 %s 内容日历生成完成", project_id)
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.COMPLETED.value,
                progress_step="done",
                message=(
                    f"已重生成 {len(selected_days)} 条内容，其余日历已保留"
                    if is_partial_regenerate
                    else f"30天日历生成完成，共 {len(content_calendar)} 条内容"
                ),
            )
            await db.commit()

        except Exception as exc:
            logger.error("日历重构: 项目 %s 重新生成失败: %s", project_id, exc, exc_info=True)
            project = await planning_repository.get_by_id(db, project_id)
            if project:
                project.status = "completed"
                await db.commit()
            await task_center_repo.update_status(
                db,
                resolved_task_key,
                status=TaskStatus.FAILED.value,
                progress_step="failed",
                message="日历重生成失败",
                error_message=str(exc),
            )
            await db.commit()
        finally:
            cancellation_registry.clear(project_id)
