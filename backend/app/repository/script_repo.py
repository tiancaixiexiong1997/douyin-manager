"""
数据访问层：视频脚本提取记录
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.models.database import ScriptExtraction, ExtractionStatus


class ScriptExtractionRepository:
    """提取记录操作库"""

    async def create(self, db: AsyncSession, data: dict) -> ScriptExtraction:
        """创建初始提取记录"""
        record = ScriptExtraction(**data)
        db.add(record)
        return record

    async def get_by_id(self, db: AsyncSession, extraction_id: str) -> Optional[ScriptExtraction]:
        """根据 ID 获取提取记录"""
        result = await db.execute(
            select(ScriptExtraction).where(ScriptExtraction.id == extraction_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> List[ScriptExtraction]:
        """获取历史提取记录列表，按创建时间倒序"""
        result = await db.execute(
            select(ScriptExtraction)
            .order_by(ScriptExtraction.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, db: AsyncSession, extraction_id: str, update_data: dict) -> Optional[ScriptExtraction]:
        """更新提取记录"""
        record = await self.get_by_id(db, extraction_id)
        if record:
            for key, value in update_data.items():
                setattr(record, key, value)
        return record

    async def update_status(self, db: AsyncSession, extraction_id: str, status: ExtractionStatus, error_message: str = None):
        """快捷更新状态"""
        update_data = {"status": status}
        if error_message is not None:
            update_data["error_message"] = error_message
        await self.update(db, extraction_id, update_data)

    async def mark_retry(self, db: AsyncSession, extraction_id: str, retry_count: int, error_message: str):
        """标记一次重试并记录最近错误。"""
        await self.update(
            db,
            extraction_id,
            {
                "retry_count": retry_count,
                "error_message": error_message,
                "status": ExtractionStatus.PENDING,
            },
        )

    async def delete(self, db: AsyncSession, extraction_id: str) -> bool:
        """删除提取记录"""
        record = await self.get_by_id(db, extraction_id)
        if record:
            await db.delete(record)
            return True
        return False


script_repo = ScriptExtractionRepository()
