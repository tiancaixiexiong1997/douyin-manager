"""日历排期 API 端点。"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_member_or_admin
from app.config import settings
from app.models.database import User
from app.models.db_session import get_db
from app.repository.operation_log_repo import operation_log_repo
from app.repository.schedule_repo import schedule_repository
from app.schemas.schedule import (
    ScheduleEntryCreateRequest,
    ScheduleEntryResponse,
    ScheduleEntryUpdateRequest,
)

router = APIRouter()


def _today_in_app_timezone() -> date:
    try:
        tz = ZoneInfo(settings.APP_TIMEZONE)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).date()


def _ensure_not_past_schedule_date(target_date: date) -> None:
    if target_date < _today_in_app_timezone():
        raise HTTPException(status_code=400, detail="过去日期不允许新增或调整排期")


@router.get("", response_model=list[ScheduleEntryResponse], summary="获取日历排期列表")
async def list_schedule_entries(
    start_date: date | None = Query(None, description="开始日期（YYYY-MM-DD）"),
    end_date: date | None = Query(None, description="结束日期（YYYY-MM-DD）"),
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(500, ge=1, le=2000, description="返回条数"),
    db: AsyncSession = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    return await schedule_repository.list_all(
        db,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ScheduleEntryResponse, summary="创建日历排期")
async def create_schedule_entry(
    request: ScheduleEntryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="排期标题不能为空")
    _ensure_not_past_schedule_date(request.schedule_date)
    entry = await schedule_repository.create(
        db,
        {
            "schedule_date": request.schedule_date,
            "title": title,
            "content_type": (request.content_type or "").strip() or None,
            "notes": (request.notes or "").strip() or None,
            "done": request.done,
            "created_by_user_id": current_user.id,
            "created_by": current_user.username,
        },
    )
    await operation_log_repo.create(
        db,
        action="schedule.create",
        entity_type="schedule_entry",
        entity_id=entry.id,
        actor=current_user.username,
        detail="创建日历排期",
        extra={
            "schedule_date": str(entry.schedule_date),
            "title": entry.title,
            "content_type": entry.content_type,
        },
    )
    return entry


@router.patch("/{entry_id}", response_model=ScheduleEntryResponse, summary="更新日历排期")
async def update_schedule_entry(
    entry_id: str,
    request: ScheduleEntryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    data = request.model_dump(exclude_none=True)
    if "title" in data:
        data["title"] = data["title"].strip()
        if not data["title"]:
            raise HTTPException(status_code=400, detail="排期标题不能为空")
    if "content_type" in data:
        data["content_type"] = (data["content_type"] or "").strip() or None
    if "notes" in data:
        data["notes"] = (data["notes"] or "").strip() or None
    if "schedule_date" in data:
        _ensure_not_past_schedule_date(data["schedule_date"])
    if not data:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    entry = await schedule_repository.update(db, entry_id, data)
    if not entry:
        raise HTTPException(status_code=404, detail="排期不存在")
    await operation_log_repo.create(
        db,
        action="schedule.update",
        entity_type="schedule_entry",
        entity_id=entry.id,
        actor=current_user.username,
        detail="更新日历排期",
        extra=data,
    )
    return entry


@router.delete("/{entry_id}", summary="删除日历排期")
async def delete_schedule_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member_or_admin),
):
    existing = await schedule_repository.get_by_id(db, entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="排期不存在")
    success = await schedule_repository.delete(db, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="排期不存在")
    await operation_log_repo.create(
        db,
        action="schedule.delete",
        entity_type="schedule_entry",
        entity_id=entry_id,
        actor=current_user.username,
        detail="删除日历排期",
        extra={"title": existing.title, "schedule_date": str(existing.schedule_date)},
    )
    return {"message": "删除成功"}
