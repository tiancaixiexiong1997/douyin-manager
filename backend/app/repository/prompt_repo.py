"""提示词版本、A/B 实验与运行记录 Repository。"""
from __future__ import annotations

from typing import Optional
from sqlalchemy import desc, select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import PromptABExperiment, PromptRun, PromptVersion


class PromptRepository:
    async def list_versions(self, db: AsyncSession, scene_key: str) -> list[PromptVersion]:
        result = await db.execute(
            select(PromptVersion)
            .where(PromptVersion.scene_key == scene_key)
            .order_by(desc(PromptVersion.created_at))
        )
        return list(result.scalars().all())

    async def get_version(self, db: AsyncSession, version_id: str) -> Optional[PromptVersion]:
        result = await db.execute(select(PromptVersion).where(PromptVersion.id == version_id))
        return result.scalar_one_or_none()

    async def get_active_version(self, db: AsyncSession, scene_key: str) -> Optional[PromptVersion]:
        result = await db.execute(
            select(PromptVersion)
            .where(
                PromptVersion.scene_key == scene_key,
                PromptVersion.is_active.is_(True),
            )
            .order_by(desc(PromptVersion.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_version(self, db: AsyncSession, data: dict) -> PromptVersion:
        item = PromptVersion(**data)
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def activate_version(self, db: AsyncSession, version_id: str) -> Optional[PromptVersion]:
        version = await self.get_version(db, version_id)
        if not version:
            return None
        await db.execute(
            PromptVersion.__table__.update()
            .where(
                and_(
                    PromptVersion.scene_key == version.scene_key,
                    PromptVersion.id != version.id,
                )
            )
            .values(is_active=False)
        )
        version.is_active = True
        await db.flush()
        return version

    async def list_experiments(self, db: AsyncSession, scene_key: str) -> list[PromptABExperiment]:
        result = await db.execute(
            select(PromptABExperiment)
            .where(PromptABExperiment.scene_key == scene_key)
            .order_by(desc(PromptABExperiment.updated_at))
        )
        return list(result.scalars().all())

    async def get_experiment(self, db: AsyncSession, experiment_id: str) -> Optional[PromptABExperiment]:
        result = await db.execute(select(PromptABExperiment).where(PromptABExperiment.id == experiment_id))
        return result.scalar_one_or_none()

    async def get_active_experiment(self, db: AsyncSession, scene_key: str) -> Optional[PromptABExperiment]:
        result = await db.execute(
            select(PromptABExperiment)
            .where(
                PromptABExperiment.scene_key == scene_key,
                PromptABExperiment.is_active.is_(True),
            )
            .order_by(desc(PromptABExperiment.updated_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_experiment(self, db: AsyncSession, data: dict) -> PromptABExperiment:
        exp = PromptABExperiment(**data)
        db.add(exp)
        await db.flush()
        await db.refresh(exp)
        return exp

    async def set_experiment_active(self, db: AsyncSession, experiment_id: str, is_active: bool) -> Optional[PromptABExperiment]:
        exp = await self.get_experiment(db, experiment_id)
        if not exp:
            return None
        if is_active:
            await db.execute(
                PromptABExperiment.__table__.update()
                .where(
                    and_(
                        PromptABExperiment.scene_key == exp.scene_key,
                        PromptABExperiment.id != exp.id,
                    )
                )
                .values(is_active=False)
            )
        exp.is_active = is_active
        await db.flush()
        return exp

    async def create_run(self, db: AsyncSession, data: dict) -> PromptRun:
        run = PromptRun(**data)
        db.add(run)
        await db.flush()
        await db.refresh(run)
        return run

    async def list_runs(
        self,
        db: AsyncSession,
        *,
        scene_key: Optional[str] = None,
        prompt_version_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PromptRun]:
        stmt = select(PromptRun)
        if scene_key:
            stmt = stmt.where(PromptRun.scene_key == scene_key)
        if prompt_version_id:
            stmt = stmt.where(PromptRun.prompt_version_id == prompt_version_id)
        stmt = stmt.order_by(desc(PromptRun.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_run(self, db: AsyncSession, run_id: str) -> Optional[PromptRun]:
        result = await db.execute(select(PromptRun).where(PromptRun.id == run_id))
        return result.scalar_one_or_none()

    async def compare_versions(self, db: AsyncSession, version_a_id: str, version_b_id: str) -> dict:
        async def _metrics(version_id: str) -> dict:
            rows = await db.execute(
                select(
                    func.count(PromptRun.id),
                    func.avg(PromptRun.score),
                    func.sum(case((PromptRun.status == "success", 1), else_=0)),
                ).where(PromptRun.prompt_version_id == version_id)
            )
            count, avg_score, success_count = rows.one()
            total = int(count or 0)
            success = int(success_count or 0)
            return {
                "version_id": version_id,
                "runs": total,
                "avg_score": float(avg_score) if avg_score is not None else None,
                "success_rate": (success / total) if total > 0 else 0.0,
            }

        return {
            "version_a": await _metrics(version_a_id),
            "version_b": await _metrics(version_b_id),
        }


prompt_repo = PromptRepository()
