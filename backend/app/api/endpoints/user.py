"""用户管理 API：管理员管理成员账号。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_admin
from app.models.database import User, UserRole
from app.models.db_session import get_db
from app.repository.operation_log_repo import operation_log_repo
from app.repository.user_repo import user_repository
from app.schemas.user import (
    UserBatchDeleteRequest,
    UserBatchStatusRequest,
    UserCreateRequest,
    UserListItemResponse,
    UserListResponse,
    UserResetPasswordRequest,
    UserUpdateRequest,
)
from app.services.auth_service import auth_service

router = APIRouter()


@router.get("", response_model=UserListResponse, summary="获取用户列表")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    keyword: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "asc",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _ = current_user
    if role is not None:
        allowed_roles = {UserRole.ADMIN.value, UserRole.MEMBER.value, UserRole.VIEWER.value}
        if role not in allowed_roles:
            raise HTTPException(status_code=400, detail="无效的角色筛选值")
    allowed_sort_fields = {"created_at", "username", "role", "is_active"}
    if sort_by not in allowed_sort_fields:
        raise HTTPException(status_code=400, detail="无效的排序字段")
    if sort_order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="无效的排序方向")
    limit = max(1, min(limit, 200))
    normalized_skip = max(0, skip)
    items = await user_repository.list_all(
        db,
        skip=normalized_skip,
        limit=limit,
        keyword=keyword,
        role=role,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    total = await user_repository.count_all(
        db,
        keyword=keyword,
        role=role,
        is_active=is_active,
    )
    return UserListResponse(items=items, total=total, skip=normalized_skip, limit=limit)


@router.patch("/batch-status", summary="批量更新用户启用状态")
async def batch_update_user_status(
    request: UserBatchStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    updated = 0
    for user_id in request.user_ids:
        target = await user_repository.get_by_id(db, user_id)
        if not target:
            continue
        if target.username == current_user.username and request.is_active is False:
            continue
        await user_repository.update(db, user_id, {"is_active": request.is_active})
        updated += 1

    await operation_log_repo.create(
        db,
        action="user.batch_status",
        entity_type="user",
        actor=current_user.username,
        detail=f"批量更新用户状态，共影响 {updated} 个账号",
        extra={"is_active": request.is_active, "count": updated},
    )
    return {"message": f"已更新 {updated} 个用户状态", "updated": updated}


@router.post("/batch-delete", summary="批量删除用户")
async def batch_delete_users(
    request: UserBatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    all_users = await user_repository.list_all(db, skip=0, limit=2000)
    id_map = {item.id: item for item in all_users}
    active_admin_count = sum(1 for item in all_users if item.role == UserRole.ADMIN.value and item.is_active)

    deleted = 0
    skipped = 0
    for user_id in request.user_ids:
        target = id_map.get(user_id)
        if not target:
            skipped += 1
            continue
        if target.username == current_user.username:
            skipped += 1
            continue
        if target.role == UserRole.ADMIN.value and target.is_active:
            if active_admin_count <= 1:
                skipped += 1
                continue
            active_admin_count -= 1

        success = await user_repository.delete(db, user_id)
        if success:
            deleted += 1
        else:
            skipped += 1

    await operation_log_repo.create(
        db,
        action="user.batch_delete",
        entity_type="user",
        actor=current_user.username,
        detail=f"批量删除用户，成功 {deleted}，跳过 {skipped}",
        extra={"deleted": deleted, "skipped": skipped},
    )
    return {"message": f"批量删除完成：成功 {deleted}，跳过 {skipped}", "deleted": deleted, "skipped": skipped}


@router.post("", response_model=UserListItemResponse, summary="创建用户")
async def create_user(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    allowed_roles = {UserRole.ADMIN.value, UserRole.MEMBER.value, UserRole.VIEWER.value}
    if request.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="无效的角色类型")

    existing = await user_repository.get_by_username(db, request.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = await user_repository.create(
        db,
        {
            "username": request.username,
            "password_hash": auth_service.hash_password(request.password),
            "role": request.role,
            "is_active": request.is_active,
        },
    )
    await operation_log_repo.create(
        db,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        actor=current_user.username,
        detail=f"创建用户 {user.username}",
        extra={"role": user.role, "is_active": user.is_active},
    )
    return user


@router.patch("/{user_id}", response_model=UserListItemResponse, summary="更新用户角色/状态")
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target_user = await user_repository.get_by_id(db, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if target_user.username == current_user.username and request.is_active is False:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账号")

    update_data: dict = {}
    if request.role is not None:
        allowed_roles = {UserRole.ADMIN.value, UserRole.MEMBER.value, UserRole.VIEWER.value}
        if request.role not in allowed_roles:
            raise HTTPException(status_code=400, detail="无效的角色类型")
        update_data["role"] = request.role
    if request.is_active is not None:
        update_data["is_active"] = request.is_active

    if not update_data:
        raise HTTPException(status_code=400, detail="没有可更新的字段")

    user = await user_repository.update(db, user_id, update_data)
    await operation_log_repo.create(
        db,
        action="user.update",
        entity_type="user",
        entity_id=user_id,
        actor=current_user.username,
        detail=f"更新用户 {target_user.username}",
        extra=update_data,
    )
    return user


@router.post("/{user_id}/reset-password", summary="重置用户密码")
async def reset_user_password(
    user_id: str,
    request: UserResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await user_repository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await user_repository.update(
        db,
        user_id,
        {"password_hash": auth_service.hash_password(request.password)},
    )
    await operation_log_repo.create(
        db,
        action="user.reset_password",
        entity_type="user",
        entity_id=user_id,
        actor=current_user.username,
        detail=f"重置用户 {user.username} 的密码",
    )
    return {"message": "密码已重置"}


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = await user_repository.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")

    if user.role == UserRole.ADMIN.value:
        all_users = await user_repository.list_all(db)
        active_admin_count = sum(1 for item in all_users if item.role == UserRole.ADMIN.value and item.is_active)
        if active_admin_count <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个启用中的管理员账号")

    success = await user_repository.delete(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")

    await operation_log_repo.create(
        db,
        action="user.delete",
        entity_type="user",
        entity_id=user_id,
        actor=current_user.username,
        detail=f"删除用户 {user.username}",
        extra={"role": user.role},
    )
    return {"message": "用户已删除"}
