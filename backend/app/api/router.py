"""
API 路由聚合
"""
from fastapi import APIRouter, Depends
from app.api.deps.auth import require_admin, require_member_or_admin
from app.api.endpoints import (
    ai_prompt,
    auth,
    blogger,
    planning,
    script,
    setting,
    download,
    user,
    log,
    schedule,
    task_center,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(setting.public_router, prefix="/settings", tags=["系统设置"])
api_router.include_router(blogger.router, prefix="/bloggers", tags=["博主IP库"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(planning.router, prefix="/planning", tags=["账号策划"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(script.router, prefix="/script", tags=["视频脚本提取复刻"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(setting.router, prefix="/settings", tags=["系统设置"], dependencies=[Depends(require_admin)])
api_router.include_router(ai_prompt.router, prefix="/ai-prompts", tags=["AI能力管理"], dependencies=[Depends(require_admin)])
api_router.include_router(download.router, prefix="/download", tags=["无水印下载"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(schedule.router, prefix="/schedules", tags=["日历排期"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(task_center.router, prefix="/tasks", tags=["任务中心"], dependencies=[Depends(require_member_or_admin)])
api_router.include_router(user.router, prefix="/users", tags=["用户管理"], dependencies=[Depends(require_admin)])
api_router.include_router(log.router, prefix="/logs", tags=["操作日志"], dependencies=[Depends(require_admin)])
