"""
AI二创API端点
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from app.ai_service import AICreativeService
from crawlers.hybrid.hybrid_crawler import HybridCrawler
import os
import httpx

router = APIRouter()
ai_service = AICreativeService()
hybrid_crawler = HybridCrawler()


class CreativeRequest(BaseModel):
    """二创请求模型"""
    video_url: str
    user_prompt: str
    creative_type: Optional[str] = "general"


@router.post("/ai_creative", tags=["AI-Creative"])
async def ai_creative_analysis(request: CreativeRequest):
    """
    AI视频二创分析接口

    Args:
        video_url: 抖音/TikTok视频链接
        user_prompt: 用户二创需求描述
        creative_type: 二创类型 (general/script/highlights/commentary)

    Returns:
        AI分析结果和二创建议
    """
    try:
        # 1. 使用hybrid_crawler解析视频（使用minimal=True获取结构化数据）
        video_data = await hybrid_crawler.hybrid_parsing_single_video(request.video_url, minimal=True)

        if not video_data:
            raise HTTPException(status_code=400, detail="视频解析失败")

        # 2. 获取平台和基本信息
        platform = video_data.get('platform', '')
        desc = video_data.get('desc', '')
        author = video_data.get('author', {})
        author_name = author.get('nickname', '') if isinstance(author, dict) else str(author)

        # 3. 获取无水印视频URL
        video_url = None

        if platform == 'douyin':
            video_url = video_data.get('video_data', {}).get('nwm_video_url')
        elif platform == 'tiktok':
            video_url = video_data.get('video_data', {}).get('nwm_video_url')
        elif platform == 'bilibili':
            # Bilibili需要特殊处理
            video_url = video_data.get('video_data', {}).get('video_url')

        if not video_url:
            raise HTTPException(status_code=400, detail="无法获取视频URL")

        # 3. 调用AI服务分析视频（下载后分析）
        ai_result = await ai_service.analyze_video_from_url(
            video_url=video_url,
            video_title=desc,
            user_prompt=request.user_prompt,
            creative_type=request.creative_type
        )

        if not ai_result.get('success'):
            raise HTTPException(
                status_code=500,
                detail=ai_result.get('error', 'AI分析失败')
            )

        # 4. 返回完整结果
        return {
            "status": "success",
            "message": "AI二创分析完成",
            "data": {
                "video_info": {
                    "platform": platform,
                    "title": desc,
                    "author": author_name,
                    "video_url": video_url
                },
                "ai_analysis": {
                    "content": ai_result.get('content'),
                    "model": ai_result.get('model'),
                    "usage": ai_result.get('usage')
                },
                "creative_type": request.creative_type,
                "user_prompt": request.user_prompt
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/ai_creative_simple", tags=["AI-Creative"])
async def ai_creative_simple(
    url: str = Query(..., description="视频链接"),
    prompt: str = Query(..., description="二创需求"),
    type: str = Query("general", description="二创类型: general/script/highlights/commentary")
):
    """
    AI视频二创分析接口（GET方式，方便测试）

    Args:
        url: 抖音/TikTok视频链接
        prompt: 用户二创需求描述
        type: 二创类型

    Returns:
        AI分析结果和二创建议
    """
    request = CreativeRequest(
        video_url=url,
        user_prompt=prompt,
        creative_type=type
    )
    return await ai_creative_analysis(request)
