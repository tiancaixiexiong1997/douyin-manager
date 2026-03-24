from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.models.database import User
from app.models.db_session import get_db
from app.repository.operation_log_repo import operation_log_repo
from app.repository.performance_repo import performance_repo
from app.repository.planning_repo import planning_repository
from app.schemas.planning import (
    ContentItemResponse,
    ContentPerformanceCreateRequest,
    ContentPerformanceResponse,
    ContentPerformanceSummaryResponse,
    ContentPerformanceUpdateRequest,
    NextTopicBatchResponse,
    PerformanceRecapResponse,
)
from app.services.ai_analysis_service import ai_analysis_service
from app.services.planning_calendar_utils import normalize_content_type
from app.services.planning_performance_utils import (
    build_next_topic_calendar_item,
    normalize_next_topic_batch,
    normalize_performance_recap,
    serialize_existing_content_items,
    serialize_performance_rows,
)

router = APIRouter()


@router.get("/{project_id}/performance", response_model=list[ContentPerformanceResponse], summary="获取发布回流数据")
async def list_project_performance(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await performance_repo.list_by_project(db, project_id)


@router.post("/{project_id}/performance", response_model=ContentPerformanceResponse, summary="新增发布回流记录")
async def create_project_performance(
    project_id: str,
    request: ContentPerformanceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    record = await performance_repo.create(
        db,
        {
            "project_id": project_id,
            **request.model_dump(),
        },
    )
    await operation_log_repo.create(
        db,
        action="planning.performance.create",
        entity_type="content_performance",
        entity_id=record.id,
        actor=current_user.username,
        detail="新增发布回流记录",
        extra={"project_id": project_id},
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.patch("/{project_id}/performance/{performance_id}", response_model=ContentPerformanceResponse, summary="更新发布回流记录")
async def update_project_performance(
    project_id: str,
    performance_id: str,
    request: ContentPerformanceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = request.model_dump(exclude_none=True)
    record = await performance_repo.update(db, performance_id, data)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="回流记录不存在")
    await operation_log_repo.create(
        db,
        action="planning.performance.update",
        entity_type="content_performance",
        entity_id=record.id,
        actor=current_user.username,
        detail="更新发布回流记录",
        extra={"project_id": project_id, "fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{project_id}/performance/{performance_id}", summary="删除发布回流记录")
async def delete_project_performance(
    project_id: str,
    performance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    record = await performance_repo.get_by_id(db, performance_id)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="回流记录不存在")
    await performance_repo.delete(db, performance_id)
    await operation_log_repo.create(
        db,
        action="planning.performance.delete",
        entity_type="content_performance",
        entity_id=performance_id,
        actor=current_user.username,
        detail="删除发布回流记录",
        extra={"project_id": project_id},
    )
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{project_id}/performance-summary", response_model=ContentPerformanceSummaryResponse, summary="获取发布回流汇总")
async def get_project_performance_summary(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return await performance_repo.summary_by_project(
        db,
        project_id,
        planned_content_count=len(project.content_items or []),
    )


@router.post("/{project_id}/performance-recap", response_model=PerformanceRecapResponse, summary="生成 AI 发布复盘建议")
async def generate_project_performance_recap(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法做 AI 复盘")

    performance_rows = await performance_repo.list_by_project(db, project_id)
    if not performance_rows:
        raise HTTPException(status_code=400, detail="请先录入至少 1 条发布回流数据")

    performance_summary = await performance_repo.summary_by_project(
        db,
        project_id,
        planned_content_count=len(project.content_items or []),
    )
    ai_result = await ai_analysis_service.generate_performance_recap(
        project_context={
            "client_name": project.client_name,
            "industry": project.industry,
            "target_audience": project.target_audience,
            "business_goal": project.business_goal,
            "planned_content_count": len(project.content_items or []),
        },
        account_plan=project.account_plan or {},
        performance_summary=performance_summary,
        performance_rows=serialize_performance_rows(project, performance_rows),
        run_context={"entity_type": "planning_project", "entity_id": project_id},
        db=db,
    )
    recap = normalize_performance_recap(ai_result if isinstance(ai_result, dict) else {})

    account_plan = dict(project.account_plan or {})
    account_plan["performance_recap"] = recap
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.performance_recap.generate",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="生成 AI 发布复盘建议",
        extra={"performance_items": len(performance_rows)},
    )
    await db.commit()
    await db.refresh(project)
    return recap


@router.post("/{project_id}/next-topic-batch", response_model=NextTopicBatchResponse, summary="生成下一批10条选题")
async def generate_project_next_topic_batch(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.account_plan:
        raise HTTPException(status_code=400, detail="账号策划尚未生成，无法生成下一批选题")

    performance_recap = (
        project.account_plan.get("performance_recap")
        if isinstance(project.account_plan, dict)
        else None
    )
    if not isinstance(performance_recap, dict):
        raise HTTPException(status_code=400, detail="请先生成 AI 发布复盘")

    ai_result = await ai_analysis_service.generate_next_topic_batch(
        project_context={
            "client_name": project.client_name,
            "industry": project.industry,
            "target_audience": project.target_audience,
            "business_goal": project.business_goal,
        },
        account_plan=project.account_plan or {},
        performance_recap=performance_recap,
        existing_content_items=serialize_existing_content_items(project),
        run_context={"entity_type": "planning_project", "entity_id": project_id},
        db=db,
    )
    next_topic_batch = normalize_next_topic_batch(ai_result if isinstance(ai_result, dict) else {})

    account_plan = dict(project.account_plan or {})
    account_plan["next_topic_batch"] = next_topic_batch
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.next_topic_batch.generate",
        entity_type="planning_project",
        entity_id=project_id,
        actor=current_user.username,
        detail="生成下一批10条选题",
        extra={"item_count": len(next_topic_batch["items"])},
    )
    await db.commit()
    await db.refresh(project)
    return next_topic_batch


@router.post("/{project_id}/next-topic-batch/{item_index}/import", response_model=ContentItemResponse, summary="将选题加入内容日历")
async def import_next_topic_batch_item(
    project_id: str,
    item_index: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    project = await planning_repository.get_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not isinstance(project.account_plan, dict):
        raise HTTPException(status_code=400, detail="项目中暂无可导入的选题批次")

    next_topic_batch = project.account_plan.get("next_topic_batch")
    if not isinstance(next_topic_batch, dict) or not isinstance(next_topic_batch.get("items"), list):
        raise HTTPException(status_code=400, detail="请先生成下一批选题")

    items = [dict(item) for item in next_topic_batch.get("items", []) if isinstance(item, dict)]
    if item_index < 0 or item_index >= len(items):
        raise HTTPException(status_code=404, detail="选题不存在")

    batch_item = items[item_index]
    if batch_item.get("imported_content_item_id"):
        raise HTTPException(status_code=400, detail="这条选题已经加入内容日历")

    next_day_number = max((item.day_number for item in project.content_items or []), default=0) + 1
    content_item = await planning_repository.add_content_item(
        db,
        {
            "project_id": project_id,
            "day_number": next_day_number,
            "title_direction": batch_item.get("title_direction", ""),
            "content_type": normalize_content_type(batch_item.get("content_type")),
            "tags": [batch_item.get("content_pillar")] if batch_item.get("content_pillar") else [],
        },
    )

    updated_calendar = list(project.content_calendar or [])
    updated_calendar.append(build_next_topic_calendar_item(batch_item, next_day_number))
    project.content_calendar = updated_calendar

    batch_item["imported_content_item_id"] = content_item.id
    batch_item["imported_day_number"] = next_day_number
    batch_item["imported_at"] = datetime.utcnow().isoformat()
    items[item_index] = batch_item

    account_plan = dict(project.account_plan or {})
    account_plan["next_topic_batch"] = {
        **next_topic_batch,
        "items": items,
    }
    project.account_plan = account_plan

    await operation_log_repo.create(
        db,
        action="planning.next_topic_batch.import",
        entity_type="content_item",
        entity_id=content_item.id,
        actor=current_user.username,
        detail="将下一批选题加入内容日历",
        extra={"project_id": project_id, "item_index": item_index, "day_number": next_day_number},
    )
    await db.commit()
    await db.refresh(content_item)
    return content_item
