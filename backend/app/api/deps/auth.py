"""认证依赖：校验 Bearer Token 并限制管理员访问。"""
from collections.abc import Callable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.models.database import User, UserRole
from app.models.db_session import AsyncSessionLocal
from app.repository.user_repo import user_repository
from app.services.auth_service import auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> User:
    resolved_token = token or request.cookies.get(settings.ACCESS_COOKIE_NAME)

    if not resolved_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未授权，请先登录")

    payload = auth_service.decode_access_token(resolved_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的登录凭证")

    async with AsyncSessionLocal() as db:
        user = await user_repository.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return current_user

    return checker


async def require_admin(
    current_user: User = Depends(require_roles(UserRole.ADMIN.value)),
) -> User:
    return current_user


async def require_member_or_admin(
    current_user: User = Depends(require_roles(UserRole.ADMIN.value, UserRole.MEMBER.value)),
) -> User:
    return current_user


async def require_authenticated(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in {UserRole.ADMIN.value, UserRole.MEMBER.value, UserRole.VIEWER.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    return current_user
