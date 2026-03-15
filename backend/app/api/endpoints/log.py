"""操作日志 API。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_admin
from app.models.database import User
from app.models.db_session import get_db
from app.repository.operation_log_repo import operation_log_repo
from app.schemas.log import OperationLogResponse, OperationLogPagedResponse

router = APIRouter()


@router.get("", response_model=list[OperationLogResponse] | OperationLogPagedResponse, summary="获取系统操作日志")
async def list_logs(
    skip: int = Query(0, ge=0, description="跳过条数"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限"),
    action: str | None = Query(None, description="按动作模糊筛选"),
    actor: str | None = Query(None, description="按操作人模糊筛选"),
    with_meta: bool = Query(False, description="是否返回分页元信息（total/has_more）"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _ = current_user
    normalized_action = (action or "").strip() or None
    normalized_actor = (actor or "").strip() or None
    items = await operation_log_repo.list_all(
        db,
        skip=skip,
        limit=limit,
        action=normalized_action,
        actor=normalized_actor,
    )
    if not with_meta:
        return items

    total = await operation_log_repo.count_all(
        db,
        action=normalized_action,
        actor=normalized_actor,
    )
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(items) < total,
    }
