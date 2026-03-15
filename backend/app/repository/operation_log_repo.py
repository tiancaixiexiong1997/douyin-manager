"""操作日志仓库。"""
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import OperationLog


class OperationLogRepository:
    async def create(
        self,
        db: AsyncSession,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor: str = "system",
        detail: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> OperationLog:
        record = OperationLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            detail=detail,
            extra=extra,
        )
        db.add(record)
        return record

    async def list_all(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        action: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> list[OperationLog]:
        stmt = select(OperationLog).order_by(OperationLog.created_at.desc()).offset(skip).limit(limit)
        if action:
            stmt = stmt.where(OperationLog.action.like(f"%{action}%"))
        if actor:
            stmt = stmt.where(OperationLog.actor.like(f"%{actor}%"))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_all(
        self,
        db: AsyncSession,
        *,
        action: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(OperationLog)
        if action:
            stmt = stmt.where(OperationLog.action.like(f"%{action}%"))
        if actor:
            stmt = stmt.where(OperationLog.actor.like(f"%{actor}%"))
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)


operation_log_repo = OperationLogRepository()
