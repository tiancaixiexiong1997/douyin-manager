"""发布回流数据 Repository。"""
from __future__ import annotations

from typing import Any, Optional, Sequence
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ContentPerformance


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _safe_rate(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return float(numerator / denominator * 100)


def _engagement_rate(item: Any) -> float | None:
    return _safe_rate(
        int(getattr(item, "likes", 0) or 0) + int(getattr(item, "comments", 0) or 0) + int(getattr(item, "shares", 0) or 0),
        int(getattr(item, "views", 0) or 0),
    )


def _short_title(title: str, limit: int = 20) -> str:
    text = (title or "").strip()
    if len(text) <= limit:
        return text or "这条内容"
    return f"{text[:limit].rstrip()}..."


def _pick_best(rows: Sequence[Any], score_getter) -> Any | None:
    candidates: list[tuple[float, Any]] = []
    for row in rows:
        score = score_getter(row)
        if score is None:
            continue
        candidates.append((float(score), row))
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda pair: (
            pair[0],
            int(getattr(pair[1], "views", 0) or 0),
            int(getattr(pair[1], "likes", 0) or 0),
        ),
    )[1]


def _build_insights(
    rows: Sequence[Any],
    planned_content_count: int,
    coverage_rate: float | None,
    avg_completion_5s_rate: float | None,
    avg_completion_rate: float | None,
    avg_engagement_rate: float | None,
    total_conversions: int,
    best_view_item: Any | None,
    best_completion_item: Any | None,
    best_conversion_item: Any | None,
) -> list[dict[str, str]]:
    if not rows:
        return [
            {
                "title": "先补首批回流样本",
                "body": "先录入 3 到 5 条已发布内容的播放、完播和互动数据，复盘结论才会开始稳定。",
                "tone": "neutral",
            },
            {
                "title": "优先记录留存指标",
                "body": "建议先把 2 秒跳出率、5 秒完播率和整体完播率补齐，这三项最能帮助判断开头和内容结构。",
                "tone": "neutral",
            },
        ]

    insights: list[dict[str, str]] = []
    total_items = len(rows)

    if planned_content_count > 0 and coverage_rate is not None:
        coverage_tone = "good" if coverage_rate >= 60 else "warn"
        insights.append(
            {
                "title": "回流覆盖度",
                "body": (
                    f"当前已回流 {total_items}/{planned_content_count} 条内容，覆盖率 {coverage_rate:.1f}%。"
                    if coverage_tone == "good"
                    else f"当前仅回流 {total_items}/{planned_content_count} 条内容，建议继续补数据，避免样本过少影响判断。"
                ),
                "tone": coverage_tone,
            }
        )
    elif total_items < 3:
        insights.append(
            {
                "title": "样本量还偏少",
                "body": "当前回流内容少于 3 条，建议再补几条后再做节奏和题材判断，会更稳。",
                "tone": "warn",
            }
        )

    if best_completion_item and (avg_completion_5s_rate is not None or avg_completion_rate is not None):
        strong_retention = (
            (avg_completion_5s_rate is not None and avg_completion_5s_rate >= 45)
            or (avg_completion_rate is not None and avg_completion_rate >= 25)
        )
        completion_value = getattr(best_completion_item, "completion_rate", None)
        completion_text = f"{float(completion_value):.1f}%" if completion_value is not None else "表现最好"
        insights.append(
            {
                "title": "留存表现",
                "body": (
                    f"《{_short_title(getattr(best_completion_item, 'title', ''))}》的整体完播率最高，达到 {completion_text}，可以优先复用它的开头切入和叙事节奏。"
                    if strong_retention
                    else f"当前留存还有提升空间，完播表现最好的是《{_short_title(getattr(best_completion_item, 'title', ''))}》，可优先拆它的开头结构做变体。"
                ),
                "tone": "good" if strong_retention else "warn",
            }
        )

    if best_conversion_item and total_conversions > 0:
        insights.append(
            {
                "title": "转化线索已出现",
                "body": f"《{_short_title(getattr(best_conversion_item, 'title', ''))}》当前转化表现最好，建议优先复用它的承诺点、证明方式和 CTA 收口。",
                "tone": "good",
            }
        )
    elif avg_engagement_rate is not None:
        tone = "good" if avg_engagement_rate >= 5 else "warn"
        if best_view_item:
            body = (
                f"《{_short_title(getattr(best_view_item, 'title', ''))}》目前播放最高，适合继续扩写同题材或同钩子。"
                if tone == "good"
                else f"当前互动率约 {avg_engagement_rate:.1f}%，建议优先优化开头钩子和评论区引导，不要只看播放。"
            )
        else:
            body = "建议继续观察高播放内容的开头和评论区反馈，再决定下一轮题材加码方向。"
        insights.append(
            {
                "title": "互动与放量",
                "body": body,
                "tone": tone,
            }
        )

    return insights[:3]


def build_performance_summary_payload(
    rows: Sequence[Any],
    planned_content_count: int = 0,
) -> dict[str, Any]:
    total_items = len(rows)
    total_views = sum(int(getattr(row, "views", 0) or 0) for row in rows)
    total_likes = sum(int(getattr(row, "likes", 0) or 0) for row in rows)
    total_comments = sum(int(getattr(row, "comments", 0) or 0) for row in rows)
    total_shares = sum(int(getattr(row, "shares", 0) or 0) for row in rows)
    total_conversions = sum(int(getattr(row, "conversions", 0) or 0) for row in rows)

    avg_bounce_2s_rate = _average([float(row.bounce_2s_rate) for row in rows if getattr(row, "bounce_2s_rate", None) is not None])
    avg_completion_5s_rate = _average([float(row.completion_5s_rate) for row in rows if getattr(row, "completion_5s_rate", None) is not None])
    avg_completion_rate = _average([float(row.completion_rate) for row in rows if getattr(row, "completion_rate", None) is not None])

    coverage_rate = _safe_rate(total_items, planned_content_count) if planned_content_count > 0 else None
    avg_engagement_rate = _safe_rate(total_likes + total_comments + total_shares, total_views)
    avg_conversion_rate = _safe_rate(total_conversions, total_views)

    top_items = sorted(
        rows,
        key=lambda row: (
            int(getattr(row, "views", 0) or 0),
            int(getattr(row, "likes", 0) or 0),
            int(getattr(row, "comments", 0) or 0),
        ),
        reverse=True,
    )[:10]
    best_view_item = top_items[0] if top_items else None
    best_completion_item = _pick_best(rows, lambda row: getattr(row, "completion_rate", None))
    best_engagement_item = _pick_best(rows, _engagement_rate)
    best_conversion_item = None
    conversion_candidates = [
        row for row in rows if int(getattr(row, "conversions", 0) or 0) > 0 and int(getattr(row, "views", 0) or 0) > 0
    ]
    if conversion_candidates:
        best_conversion_item = max(
            conversion_candidates,
            key=lambda row: (
                _safe_rate(int(getattr(row, "conversions", 0) or 0), int(getattr(row, "views", 0) or 0)) or 0,
                int(getattr(row, "conversions", 0) or 0),
                int(getattr(row, "views", 0) or 0),
            ),
        )

    return {
        "total_items": total_items,
        "planned_content_count": planned_content_count,
        "coverage_rate": coverage_rate,
        "total_views": total_views,
        "avg_bounce_2s_rate": avg_bounce_2s_rate,
        "avg_completion_5s_rate": avg_completion_5s_rate,
        "avg_completion_rate": avg_completion_rate,
        "avg_engagement_rate": avg_engagement_rate,
        "avg_conversion_rate": avg_conversion_rate,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_conversions": total_conversions,
        "top_items": list(top_items),
        "best_view_item": best_view_item,
        "best_completion_item": best_completion_item,
        "best_engagement_item": best_engagement_item,
        "best_conversion_item": best_conversion_item,
        "insights": _build_insights(
            rows=rows,
            planned_content_count=planned_content_count,
            coverage_rate=coverage_rate,
            avg_completion_5s_rate=avg_completion_5s_rate,
            avg_completion_rate=avg_completion_rate,
            avg_engagement_rate=avg_engagement_rate,
            total_conversions=total_conversions,
            best_view_item=best_view_item,
            best_completion_item=best_completion_item,
            best_conversion_item=best_conversion_item,
        ),
    }


class PerformanceRepository:
    async def list_by_project(self, db: AsyncSession, project_id: str) -> list[ContentPerformance]:
        result = await db.execute(
            select(ContentPerformance)
            .where(ContentPerformance.project_id == project_id)
            .order_by(
                desc(ContentPerformance.publish_date),
                desc(ContentPerformance.updated_at),
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, performance_id: str) -> Optional[ContentPerformance]:
        result = await db.execute(
            select(ContentPerformance).where(ContentPerformance.id == performance_id)
        )
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, data: dict) -> ContentPerformance:
        item = ContentPerformance(**data)
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def update(self, db: AsyncSession, performance_id: str, data: dict) -> Optional[ContentPerformance]:
        item = await self.get_by_id(db, performance_id)
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        await db.flush()
        return item

    async def delete(self, db: AsyncSession, performance_id: str) -> bool:
        item = await self.get_by_id(db, performance_id)
        if not item:
            return False
        await db.delete(item)
        return True

    async def summary_by_project(self, db: AsyncSession, project_id: str, planned_content_count: int = 0) -> dict:
        result = await db.execute(
            select(ContentPerformance)
            .where(ContentPerformance.project_id == project_id)
            .order_by(desc(ContentPerformance.publish_date), desc(ContentPerformance.updated_at))
        )
        rows = list(result.scalars().all())
        return build_performance_summary_payload(rows, planned_content_count=planned_content_count)


performance_repo = PerformanceRepository()
