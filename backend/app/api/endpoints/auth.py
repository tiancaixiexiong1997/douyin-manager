"""认证 API：系统用户登录。"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import require_authenticated
from app.models.database import User
from app.models.db_session import get_db
from app.repository.user_repo import user_repository
from app.schemas.auth import LoginRequest, LoginResponse, CurrentUserResponse
from app.services.auth_service import auth_service
from app.services.login_rate_limiter import login_rate_limiter
from app.config import settings

router = APIRouter()


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common_kwargs = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": "/",
    }
    if settings.COOKIE_DOMAIN:
        common_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **common_kwargs,
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        **common_kwargs,
    )


def _clear_auth_cookies(response: Response) -> None:
    kwargs = {"path": "/"}
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, **kwargs)
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, **kwargs)


@router.post("/login", response_model=LoginResponse, summary="管理员登录")
async def login(payload: LoginRequest, response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    client_ip = (request.client.host if request.client else "") or "unknown"
    allowed, retry_after = login_rate_limiter.hit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录过于频繁，请在 {retry_after} 秒后重试",
        )

    user, auth_status = await auth_service.authenticate_user_with_status(db, payload.username, payload.password)
    if auth_status == "locked":
        await db.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="账号已临时锁定，请稍后再试或联系管理员")
    if auth_status == "inactive":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    if not user:
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    login_rate_limiter.reset(client_ip)
    access_token = auth_service.create_access_token(user.id, user.role, user.username)
    refresh_token = auth_service.create_refresh_token(user.id, user.role, user.username)
    _set_auth_cookies(response, access_token, refresh_token)
    return LoginResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        username=user.username,
        role=user.role,
    )


@router.post("/refresh", response_model=LoginResponse, summary="刷新登录状态")
async def refresh_token(response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    refresh = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

    payload = auth_service.decode_refresh_token(refresh)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效")

    user = await user_repository.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    access_token = auth_service.create_access_token(user.id, user.role, user.username)
    new_refresh_token = auth_service.create_refresh_token(user.id, user.role, user.username)
    _set_auth_cookies(response, access_token, new_refresh_token)
    return LoginResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        username=user.username,
        role=user.role,
    )


@router.post("/logout", summary="退出登录")
async def logout(response: Response):
    _clear_auth_cookies(response)
    return {"message": "退出成功"}


@router.get("/me", response_model=CurrentUserResponse, summary="获取当前登录用户")
async def current_user(current_user: User = Depends(require_authenticated)):
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
    )
