"""统一任务中心 Repository。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import TaskCenterItem, TaskStatus


class TaskCenterRepository:
    async def get_latest_for_entity(
        self,
        db: AsyncSession,
        *,
        entity_type: str,
        entity_id: str,
    ) -> Optional[TaskCenterItem]:
        if not hasattr(db, "execute"):
            return None
        result = await db.execute(
            select(TaskCenterItem)
            .where(
                TaskCenterItem.entity_type == entity_type,
                TaskCenterItem.entity_id == entity_id,
            )
            .order_by(desc(TaskCenterItem.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_task_key(self, db: AsyncSession, task_key: str) -> Optional[TaskCenterItem]:
        if not hasattr(db, "execute"):
            return None
        result = await db.execute(select(TaskCenterItem).where(TaskCenterItem.task_key == task_key))
        return result.scalar_one_or_none()

    async def upsert_task(
        self,
        db: AsyncSession,
        *,
        task_key: str,
        task_type: str,
        title: str,
        entity_type: str,
        entity_id: str,
        status: str = TaskStatus.QUEUED.value,
        progress_step: Optional[str] = None,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TaskCenterItem]:
        if not hasattr(db, "execute"):
            return None
        task = await self.get_by_task_key(db, task_key)
        if not task:
            task = TaskCenterItem(
                task_key=task_key,
                task_type=task_type,
                title=title,
                entity_type=entity_type,
                entity_id=entity_id,
                status=status,
                progress_step=progress_step,
                message=message,
                error_message=error_message,
            )
            if status == TaskStatus.RUNNING.value:
                task.started_at = datetime.utcnow()
            if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
                now = datetime.utcnow()
                task.started_at = task.started_at or now
                task.finished_at = now
            db.add(task)
            await db.flush()
            await db.refresh(task)
            return task

        task.task_type = task_type
        task.title = title
        task.entity_type = entity_type
        task.entity_id = entity_id
        task.status = status
        task.progress_step = progress_step
        task.message = message
        task.error_message = error_message
        if status == TaskStatus.RUNNING.value:
            task.started_at = task.started_at or datetime.utcnow()
            task.finished_at = None
        if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
            task.finished_at = datetime.utcnow()
            task.started_at = task.started_at or task.finished_at
        await db.flush()
        return task

    async def update_status(
        self,
        db: AsyncSession,
        task_key: str,
        *,
        status: str,
        progress_step: Optional[str] = None,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TaskCenterItem]:
        if not hasattr(db, "execute"):
            return None
        task = await self.get_by_task_key(db, task_key)
        if not task:
            return None
        task.status = status
        if progress_step is not None:
            task.progress_step = progress_step
        if message is not None:
            task.message = message
        if error_message is not None:
            task.error_message = error_message
        if status == TaskStatus.RUNNING.value:
            task.started_at = task.started_at or datetime.utcnow()
            task.finished_at = None
        if status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
            task.finished_at = datetime.utcnow()
            task.started_at = task.started_at or task.finished_at
        await db.flush()
        return task

    async def list_tasks(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> list[TaskCenterItem]:
        if not hasattr(db, "execute"):
            return []
        stmt = select(TaskCenterItem)
        if status:
            stmt = stmt.where(TaskCenterItem.status == status)
        if task_type:
            stmt = stmt.where(TaskCenterItem.task_type == task_type)
        if entity_type:
            stmt = stmt.where(TaskCenterItem.entity_type == entity_type)
        stmt = stmt.order_by(desc(TaskCenterItem.updated_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_tasks(
        self,
        db: AsyncSession,
        *,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> int:
        if not hasattr(db, "execute"):
            return 0
        stmt = select(func.count()).select_from(TaskCenterItem)
        if status:
            stmt = stmt.where(TaskCenterItem.status == status)
        if task_type:
            stmt = stmt.where(TaskCenterItem.task_type == task_type)
        if entity_type:
            stmt = stmt.where(TaskCenterItem.entity_type == entity_type)
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def status_summary(self, db: AsyncSession) -> dict[str, int]:
        if not hasattr(db, "execute"):
            return {
                TaskStatus.QUEUED.value: 0,
                TaskStatus.RUNNING.value: 0,
                TaskStatus.COMPLETED.value: 0,
                TaskStatus.FAILED.value: 0,
                TaskStatus.CANCELLED.value: 0,
            }
        result = await db.execute(
            select(TaskCenterItem.status, func.count())
            .group_by(TaskCenterItem.status)
        )
        summary = {status: int(count) for status, count in result.all()}
        for status in (
            TaskStatus.QUEUED.value,
            TaskStatus.RUNNING.value,
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        ):
            summary.setdefault(status, 0)
        return summary

    async def reclaim_orphan_running_tasks(
        self,
        db: AsyncSession,
        *,
        active_task_keys: set[str],
        stale_before: datetime,
        reason: str = "任务进程中断或重启后丢失，已自动回收。",
    ) -> int:
        """
        回收“数据库显示 running，但队列中已无 started job 且超过阈值”的孤儿任务。
        """
        if not hasattr(db, "execute"):
            return 0

        result = await db.execute(
            select(TaskCenterItem).where(
                TaskCenterItem.status == TaskStatus.RUNNING.value,
                TaskCenterItem.updated_at <= stale_before,
            )
        )
        candidates = list(result.scalars().all())
        if not candidates:
            return 0

        now = datetime.utcnow()
        reclaimed = 0
        for task in candidates:
            if task.task_key in active_task_keys:
                continue
            task.status = TaskStatus.FAILED.value
            task.error_message = reason
            task.message = reason
            task.finished_at = now
            task.started_at = task.started_at or now
            reclaimed += 1

        if reclaimed > 0:
            await db.flush()
        return reclaimed


task_center_repo = TaskCenterRepository()
