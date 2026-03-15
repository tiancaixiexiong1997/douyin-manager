"""日历排期 Repository：数据库访问层。"""
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ScheduleEntry


class ScheduleRepository:
    """日历排期数据库操作。"""

    async def list_all(
        self,
        db: AsyncSession,
        start_date: date | None = None,
        end_date: date | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[ScheduleEntry]:
        stmt = select(ScheduleEntry)
        if start_date is not None:
            stmt = stmt.where(ScheduleEntry.schedule_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(ScheduleEntry.schedule_date <= end_date)

        stmt = stmt.order_by(ScheduleEntry.schedule_date.asc(), ScheduleEntry.created_at.asc()).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, entry_id: str) -> Optional[ScheduleEntry]:
        result = await db.execute(select(ScheduleEntry).where(ScheduleEntry.id == entry_id))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, data: dict) -> ScheduleEntry:
        entry = ScheduleEntry(**data)
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def update(self, db: AsyncSession, entry_id: str, data: dict) -> Optional[ScheduleEntry]:
        entry = await self.get_by_id(db, entry_id)
        if not entry:
            return None
        for key, value in data.items():
            setattr(entry, key, value)
        await db.flush()
        await db.refresh(entry)
        return entry

    async def delete(self, db: AsyncSession, entry_id: str) -> bool:
        entry = await self.get_by_id(db, entry_id)
        if not entry:
            return False
        await db.delete(entry)
        await db.flush()
        return True


schedule_repository = ScheduleRepository()

