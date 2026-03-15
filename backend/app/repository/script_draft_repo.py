"""
数据访问层：脚本拆解页草稿
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ScriptExtractionDraft


class ScriptExtractionDraftRepository:
    """脚本拆解草稿仓储（每个用户一条）。"""

    async def get_by_user_id(self, db: AsyncSession, user_id: str) -> Optional[ScriptExtractionDraft]:
        result = await db.execute(
            select(ScriptExtractionDraft).where(ScriptExtractionDraft.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        source_video_url: str,
        user_prompt: str,
        plan_id: str | None,
    ) -> ScriptExtractionDraft:
        draft = await self.get_by_user_id(db, user_id)
        if not draft:
            draft = ScriptExtractionDraft(
                user_id=user_id,
                source_video_url=source_video_url,
                user_prompt=user_prompt,
                plan_id=plan_id,
            )
            db.add(draft)
            return draft

        draft.source_video_url = source_video_url
        draft.user_prompt = user_prompt
        draft.plan_id = plan_id
        return draft


script_draft_repo = ScriptExtractionDraftRepository()
