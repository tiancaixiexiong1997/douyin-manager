"""AI 能力升级 API：提示词版本、评分、A/B 对比。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_admin
from app.models.database import User
from app.models.db_session import get_db
from app.repository.prompt_repo import prompt_repo
from app.schemas.ai_prompt import (
    PromptCompareResponse,
    PromptExperimentCreateRequest,
    PromptExperimentResponse,
    PromptExperimentUpdateRequest,
    PromptRunResponse,
    PromptRunScoreRequest,
    PromptVersionCreateRequest,
    PromptVersionResponse,
)

router = APIRouter()

PROMPT_SCENES = {
    "blogger_report": {"name": "博主IP分析", "setting_key": "BLOGGER_REPORT_PROMPT"},
    "blogger_viral_profile": {"name": "博主爆款归因", "setting_key": "BLOGGER_VIRAL_PROFILE_PROMPT"},
    "account_plan": {"name": "账号策划", "setting_key": "ACCOUNT_PLAN_PROMPT"},
    "content_calendar": {"name": "内容日历生成", "setting_key": "CONTENT_CALENDAR_PROMPT"},
    "video_script": {"name": "视频脚本生成", "setting_key": "VIDEO_SCRIPT_PROMPT"},
    "script_remake": {"name": "脚本拆解复刻", "setting_key": "SCRIPT_REMAKE_PROMPT"},
}


def _ensure_scene(scene_key: str) -> dict:
    scene = PROMPT_SCENES.get(scene_key)
    if not scene:
        raise HTTPException(status_code=400, detail=f"不支持的场景: {scene_key}")
    return scene


@router.get("/scenes", summary="获取可管理的提示词场景")
async def list_prompt_scenes(
    _current_user: User = Depends(require_admin),
):
    return [{"scene_key": key, **meta} for key, meta in PROMPT_SCENES.items()]


@router.get("/versions", response_model=list[PromptVersionResponse], summary="获取提示词版本列表")
async def list_prompt_versions(
    scene_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    _ensure_scene(scene_key)
    return await prompt_repo.list_versions(db, scene_key=scene_key)


@router.post("/versions", response_model=PromptVersionResponse, summary="创建提示词版本")
async def create_prompt_version(
    request: PromptVersionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    scene = _ensure_scene(request.scene_key)
    version = await prompt_repo.create_version(
        db,
        {
            "scene_key": request.scene_key,
            "version_label": request.version_label,
            "template_text": request.template_text,
            "source_setting_key": request.source_setting_key or scene["setting_key"],
            "created_by": current_user.username,
            "is_active": False,
        },
    )
    if request.is_active:
        version = await prompt_repo.activate_version(db, version.id) or version
    await db.commit()
    await db.refresh(version)
    return version


@router.patch("/versions/{version_id}/activate", response_model=PromptVersionResponse, summary="激活提示词版本")
async def activate_prompt_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    version = await prompt_repo.activate_version(db, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="提示词版本不存在")
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/experiments", response_model=list[PromptExperimentResponse], summary="获取 A/B 实验列表")
async def list_prompt_experiments(
    scene_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    _ensure_scene(scene_key)
    return await prompt_repo.list_experiments(db, scene_key=scene_key)


@router.post("/experiments", response_model=PromptExperimentResponse, summary="创建 A/B 实验")
async def create_prompt_experiment(
    request: PromptExperimentCreateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    _ensure_scene(request.scene_key)
    version_a = await prompt_repo.get_version(db, request.version_a_id)
    version_b = await prompt_repo.get_version(db, request.version_b_id)
    if not version_a or not version_b:
        raise HTTPException(status_code=400, detail="版本 A 或版本 B 不存在")
    if version_a.scene_key != request.scene_key or version_b.scene_key != request.scene_key:
        raise HTTPException(status_code=400, detail="A/B 版本必须属于同一场景")

    experiment = await prompt_repo.create_experiment(
        db,
        {
            "scene_key": request.scene_key,
            "name": request.name,
            "version_a_id": request.version_a_id,
            "version_b_id": request.version_b_id,
            "traffic_ratio_a": request.traffic_ratio_a,
            "is_active": False,
        },
    )
    if request.is_active:
        experiment = await prompt_repo.set_experiment_active(db, experiment.id, True) or experiment
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.patch("/experiments/{experiment_id}", response_model=PromptExperimentResponse, summary="更新 A/B 实验")
async def update_prompt_experiment(
    experiment_id: str,
    request: PromptExperimentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    exp = await prompt_repo.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="A/B 实验不存在")
    data = request.model_dump(exclude_none=True)
    if "name" in data:
        exp.name = data["name"]
    if "traffic_ratio_a" in data:
        exp.traffic_ratio_a = data["traffic_ratio_a"]
    if "is_active" in data:
        exp = await prompt_repo.set_experiment_active(db, exp.id, bool(data["is_active"])) or exp
    await db.commit()
    await db.refresh(exp)
    return exp


@router.get("/runs", response_model=list[PromptRunResponse], summary="获取 AI 生成运行记录")
async def list_prompt_runs(
    scene_key: str | None = Query(None),
    prompt_version_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    if scene_key:
        _ensure_scene(scene_key)
    return await prompt_repo.list_runs(
        db,
        scene_key=scene_key,
        prompt_version_id=prompt_version_id,
        skip=skip,
        limit=limit,
    )


@router.post("/runs/{run_id}/score", response_model=PromptRunResponse, summary="给生成结果打分")
async def score_prompt_run(
    run_id: str,
    request: PromptRunScoreRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    run = await prompt_repo.get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    run.score = request.score
    run.feedback = request.feedback
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/compare", response_model=PromptCompareResponse, summary="对比两个提示词版本表现")
async def compare_prompt_versions(
    version_a_id: str = Query(...),
    version_b_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_admin),
):
    version_a = await prompt_repo.get_version(db, version_a_id)
    version_b = await prompt_repo.get_version(db, version_b_id)
    if not version_a or not version_b:
        raise HTTPException(status_code=404, detail="版本不存在")
    if version_a.scene_key != version_b.scene_key:
        raise HTTPException(status_code=400, detail="只能比较同一场景下的版本")
    return await prompt_repo.compare_versions(db, version_a_id, version_b_id)
