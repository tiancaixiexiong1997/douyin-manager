"""
博主 Repository：数据库访问层
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, not_
from sqlalchemy.orm import selectinload

from app.models.database import Blogger, BloggerVideo

logger = logging.getLogger(__name__)


class BloggerRepository:
    """博主数据库操作"""

    async def create(self, db: AsyncSession, data: dict) -> Blogger:
        """创建博主记录"""
        blogger = Blogger(**data)
        db.add(blogger)
        await db.flush()
        await db.refresh(blogger)
        return blogger

    async def get_by_id(self, db: AsyncSession, blogger_id: str) -> Optional[Blogger]:
        """按 UUID 获取博主"""
        result = await db.execute(
            select(Blogger).where(Blogger.id == blogger_id)
            .options(selectinload(Blogger.videos))
        )
        return result.scalar_one_or_none()

    async def get_by_platform_id(self, db: AsyncSession, platform: str, blogger_id: str) -> Optional[Blogger]:
        """按平台+博主ID获取（用于重复检查）"""
        result = await db.execute(
            select(Blogger).where(
                Blogger.platform == platform,
                Blogger.blogger_id == blogger_id
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int | None = None,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> list[Blogger]:
        """获取博主列表（支持分页）"""
        stmt = select(Blogger)
        if keyword:
            like_kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Blogger.nickname.like(like_kw),
                    Blogger.signature.like(like_kw),
                    Blogger.blogger_id.like(like_kw),
                )
            )
        if platform:
            stmt = stmt.where(Blogger.platform == platform)

        stmt = stmt.order_by(Blogger.created_at.desc()).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_all(
        self,
        db: AsyncSession,
        keyword: str | None = None,
        platform: str | None = None,
    ) -> int:
        """统计博主总数"""
        stmt = select(func.count()).select_from(Blogger)
        if keyword:
            like_kw = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Blogger.nickname.like(like_kw),
                    Blogger.signature.like(like_kw),
                    Blogger.blogger_id.like(like_kw),
                )
            )
        if platform:
            stmt = stmt.where(Blogger.platform == platform)

        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)

    async def update_analysis(self, db: AsyncSession, blogger_id: str, report: dict) -> Optional[Blogger]:
        """更新博主 AI 分析报告"""
        blogger = await self.get_by_id(db, blogger_id)
        if blogger:
            blogger.analysis_report = report
            blogger.is_analyzed = True
            await db.flush()
        return blogger

    async def delete(self, db: AsyncSession, blogger_id: str) -> bool:
        """删除博主"""
        result = await db.execute(
            delete(Blogger).where(Blogger.id == blogger_id)
        )
        return result.rowcount > 0

    async def add_video(self, db: AsyncSession, data: dict) -> BloggerVideo:
        """添加博主视频"""
        video = BloggerVideo(**data)
        db.add(video)
        await db.flush()
        return video

    async def update_video_analysis(self, db: AsyncSession, video_id: str, analysis: dict) -> Optional[BloggerVideo]:
        """更新视频 AI 分析"""
        result = await db.execute(select(BloggerVideo).where(BloggerVideo.id == video_id))
        video = result.scalar_one_or_none()
        if video:
            video.ai_analysis = analysis
            video.is_analyzed = True
            await db.flush()
        return video

    async def get_videos_by_blogger(self, db: AsyncSession, blogger_id: str) -> list[BloggerVideo]:
        """获取博主所有视频"""
        result = await db.execute(
            select(BloggerVideo)
            .where(BloggerVideo.blogger_id == blogger_id)
            .order_by(BloggerVideo.like_count.desc())
        )
        return list(result.scalars().all())

    async def reset_analysis(self, db: AsyncSession, blogger_id: str) -> Optional[Blogger]:
        """重置博主分析状态（用于重新采集前）"""
        blogger = await self.get_by_id(db, blogger_id)
        if blogger:
            blogger.is_analyzed = False
            blogger.analysis_report = None
            await db.flush()
        return blogger

    async def delete_all_videos(self, db: AsyncSession, blogger_id: str) -> int:
        """删除博主普通视频记录（重新采集时清理旧数据）
        
        NOTE: 故意保留 video_id 以 'rep_' 开头的代表作深度分析记录，
        避免重采集时把用户好不容易跑完的多模态析帧结果一并清空。
        """
        result = await db.execute(
            delete(BloggerVideo).where(
                BloggerVideo.blogger_id == blogger_id,
                not_(BloggerVideo.video_id.like('rep_%'))
            )
        )
        return result.rowcount

    async def get_existing_video_ids(self, db: AsyncSession, blogger_id: str) -> set[str]:
        """获取博主已入库的视频 ID（不含代表作 rep_ 前缀）。"""
        result = await db.execute(
            select(BloggerVideo.video_id).where(
                BloggerVideo.blogger_id == blogger_id,
                not_(BloggerVideo.video_id.like("rep_%")),
            )
        )
        return {row[0] for row in result.all() if row and row[0]}

    async def count_normal_videos(self, db: AsyncSession, blogger_id: str) -> int:
        result = await db.execute(
            select(func.count(BloggerVideo.id)).where(
                BloggerVideo.blogger_id == blogger_id,
                not_(BloggerVideo.video_id.like("rep_%")),
            )
        )
        return int(result.scalar_one() or 0)

    async def update_collection_meta(
        self,
        db: AsyncSession,
        blogger_id: str,
        *,
        incremental_enabled: bool,
        last_collected_published_at: Optional[datetime] = None,
    ) -> Optional[Blogger]:
        blogger = await self.get_by_id(db, blogger_id)
        if not blogger:
            return None
        blogger.incremental_enabled = incremental_enabled
        blogger.last_collected_at = datetime.utcnow()
        if last_collected_published_at is not None:
            blogger.last_collected_published_at = last_collected_published_at
        await db.flush()
        return blogger

    async def get_rep_video(self, db: AsyncSession, blogger_id: str) -> Optional[BloggerVideo]:
        """获取博主已有的代表作深度分析视频记录（refresh 时用于复用已有分析结果）"""
        result = await db.execute(
            select(BloggerVideo).where(
                BloggerVideo.blogger_id == blogger_id,
                BloggerVideo.video_id.like('rep_%')
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def update_rep_url(self, db: AsyncSession, blogger_id: str, video_url: str) -> Optional[Blogger]:
        """更新博主的 representative_video_url 字段"""
        blogger = await self.get_by_id(db, blogger_id)
        if blogger:
            blogger.representative_video_url = video_url
            await db.flush()
        return blogger

    async def delete_rep_video(self, db: AsyncSession, blogger_id: str) -> int:
        """删除博主已有的代表作视频记录（设置新代表作前清除旧 rep_ 记录）"""
        result = await db.execute(
            delete(BloggerVideo).where(
                BloggerVideo.blogger_id == blogger_id,
                BloggerVideo.video_id.like('rep_%')
            )
        )
        return result.rowcount

    async def delete_video_by_id(self, db: AsyncSession, video_id: str) -> bool:
        """根据主键 ID 删除视频记录"""
        result = await db.execute(
            delete(BloggerVideo).where(BloggerVideo.id == video_id)
        )
        return result.rowcount > 0

    async def upsert_video_by_blogger_video_id(
        self,
        db: AsyncSession,
        *,
        blogger_id: str,
        video_id: str,
        data: dict,
    ) -> BloggerVideo:
        """按 (blogger_id, video_id) 幂等写入视频，自动清理重复脏数据。"""
        result = await db.execute(
            select(BloggerVideo)
            .where(
                BloggerVideo.blogger_id == blogger_id,
                BloggerVideo.video_id == video_id,
            )
            .order_by(BloggerVideo.created_at.asc(), BloggerVideo.id.asc())
        )
        videos = list(result.scalars().all())
        if videos:
            video = videos[0]
            # 历史脏数据去重：保留最早一条，删除其余重复记录
            for duplicate in videos[1:]:
                await db.delete(duplicate)
        else:
            video = BloggerVideo(blogger_id=blogger_id, video_id=video_id)
            db.add(video)

        for field in (
            "title",
            "description",
            "cover_url",
            "video_url",
            "like_count",
            "comment_count",
            "share_count",
            "duration",
            "published_at",
            "ai_analysis",
            "is_analyzed",
        ):
            if field in data:
                setattr(video, field, data[field])

        await db.flush()
        return video


blogger_repository = BloggerRepository()
