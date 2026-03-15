"""用户 Repository：登录鉴权与用户查询。"""
from typing import Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import User


class UserRepository:
    def _apply_filters(
        self,
        stmt,
        *,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ):
        if keyword:
            kw = f"%{keyword.lower()}%"
            stmt = stmt.where(func.lower(User.username).like(kw))
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        return stmt

    async def list_all(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 50,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "asc",
    ) -> list[User]:
        stmt = self._apply_filters(
            select(User),
            keyword=keyword,
            role=role,
            is_active=is_active,
        )
        sortable_fields = {
            "created_at": User.created_at,
            "username": User.username,
            "role": User.role,
            "is_active": User.is_active,
        }
        column = sortable_fields.get(sort_by, User.created_at)
        order_expr = desc(column) if sort_order == "desc" else asc(column)
        stmt = stmt.order_by(order_expr).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_all(
        self,
        db: AsyncSession,
        *,
        keyword: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> int:
        stmt = self._apply_filters(
            select(func.count()).select_from(User),
            keyword=keyword,
            role=role,
            is_active=is_active,
        )
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, data: dict) -> User:
        user = User(**data)
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    async def update(self, db: AsyncSession, user_id: str, update_data: dict) -> Optional[User]:
        user = await self.get_by_id(db, user_id)
        if not user:
            return None
        for key, value in update_data.items():
            setattr(user, key, value)
        await db.flush()
        await db.refresh(user)
        return user

    async def delete(self, db: AsyncSession, user_id: str) -> bool:
        user = await self.get_by_id(db, user_id)
        if not user:
            return False
        await db.delete(user)
        return True


user_repository = UserRepository()
