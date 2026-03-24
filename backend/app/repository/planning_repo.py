"""
策划项目 Repository：数据库访问层
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.models.database import PlanningProject, ContentItem

logger = logging.getLogger(__name__)


class PlanningRepository:
    """策划项目数据库操作"""

    async def create(self, db: AsyncSession, data: dict) -> PlanningProject:
        """创建策划项目"""
        project = PlanningProject(**data)
        db.add(project)
        await db.flush()
        await db.refresh(project)
        return project

    async def get_by_id(self, db: AsyncSession, project_id: str) -> Optional[PlanningProject]:
        """按 ID 获取项目（含内容条目）"""
        result = await db.execute(
            select(PlanningProject)
            .where(PlanningProject.id == project_id)
            .options(selectinload(PlanningProject.content_items))
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list[PlanningProject]:
        """获取项目列表（支持分页）"""
        stmt = select(PlanningProject)
        if keyword:
            like_kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    PlanningProject.client_name.like(like_kw),
                    PlanningProject.industry.like(like_kw),
                    PlanningProject.target_audience.like(like_kw),
                    PlanningProject.account_nickname.like(like_kw),
                )
            )
        if status:
            stmt = stmt.where(PlanningProject.status == status)

        stmt = stmt.order_by(PlanningProject.created_at.desc()).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_all(
        self,
        db: AsyncSession,
        keyword: str | None = None,
        status: str | None = None,
    ) -> int:
        """统计项目总数"""
        stmt = select(func.count()).select_from(PlanningProject)
        if keyword:
            like_kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    PlanningProject.client_name.like(like_kw),
                    PlanningProject.industry.like(like_kw),
                    PlanningProject.target_audience.like(like_kw),
                    PlanningProject.account_nickname.like(like_kw),
                )
            )
        if status:
            stmt = stmt.where(PlanningProject.status == status)

        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def update_plan_result(self, db: AsyncSession, project_id: str, account_plan: dict, content_calendar: list) -> Optional[PlanningProject]:
        """更新 AI 生成结果"""
        project = await self.get_by_id(db, project_id)
        if project:
            project.account_plan = account_plan
            project.content_calendar = content_calendar
            project.status = "completed"
            await db.flush()
        return project

    async def update_strategy_result(self, db: AsyncSession, project_id: str, account_plan: dict) -> Optional[PlanningProject]:
        """仅更新账号定位与内容策略，不生成日历。"""
        project = await self.get_by_id(db, project_id)
        if project:
            project.account_plan = account_plan
            project.content_calendar = []
            project.status = "strategy_completed"
            await db.flush()
        return project

    async def add_content_item(self, db: AsyncSession, data: dict) -> ContentItem:
        """添加内容条目"""
        item = ContentItem(**data)
        db.add(item)
        await db.flush()
        return item

    async def get_content_item(self, db: AsyncSession, item_id: str) -> Optional[ContentItem]:
        """获取内容条目"""
        result = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
        return result.scalar_one_or_none()

    async def update_script(self, db: AsyncSession, item_id: str, script: dict) -> Optional[ContentItem]:
        """更新内容条目脚本"""
        item = await self.get_content_item(db, item_id)
        if item:
            item.full_script = script
            item.is_script_generated = True
            await db.flush()
        return item

    async def update_content_item(self, db: AsyncSession, item_id: str, data: dict) -> Optional[ContentItem]:
        """部分更新内容条目字段"""
        item = await self.get_content_item(db, item_id)
        if item:
            for key, value in data.items():
                setattr(item, key, value)
            if "full_script" in data and data["full_script"]:
                item.is_script_generated = True
            await db.flush()
        return item

    async def update_project_info(self, db: AsyncSession, project_id: str, data: dict) -> Optional[PlanningProject]:
        """更新策划项目基本信息（部分更新）"""
        project = await self.get_by_id(db, project_id)
        if project:
            for key, value in data.items():
                setattr(project, key, value)
            await db.flush()
        return project

    async def delete_content_items_by_project(self, db: AsyncSession, project_id: str) -> None:
        """删除项目下的所有内容条目"""
        # Alternatively, we can use a delete query
        from sqlalchemy import delete
        await db.execute(delete(ContentItem).where(ContentItem.project_id == project_id))
        await db.flush()

    async def delete_content_items_by_days(self, db: AsyncSession, project_id: str, day_numbers: list[int]) -> None:
        """删除项目下指定天数的内容条目"""
        if not day_numbers:
            return
        from sqlalchemy import delete
        await db.execute(
            delete(ContentItem).where(
                ContentItem.project_id == project_id,
                ContentItem.day_number.in_(day_numbers),
            )
        )
        await db.flush()

    async def delete(self, db: AsyncSession, project_id: str) -> bool:
        """删除策划项目（级联删除由数据库外键或 ORM 处理）"""
        project = await self.get_by_id(db, project_id)
        if not project:
            return False
            
        await db.delete(project)
        return True


planning_repository = PlanningRepository()
