"""认证服务：密码哈希、JWT、默认管理员初始化。"""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import User, UserRole
from app.repository.user_repo import user_repository


class AuthService:
    def hash_password(self, password: str) -> str:
        """使用 PBKDF2 生成密码哈希（salt$hash）。"""
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            salt_b64, hash_b64 = stored_hash.split("$", 1)
            salt = base64.b64decode(salt_b64.encode())
            expected = base64.b64decode(hash_b64.encode())
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    def create_access_token(self, user_id: str, role: str, username: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": user_id,
            "role": role,
            "username": username,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm="HS256")

    def create_refresh_token(self, user_id: str, role: str, username: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": user_id,
            "role": role,
            "username": username,
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(payload, settings.AUTH_SECRET_KEY, algorithm="HS256")

    def decode_access_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, settings.AUTH_SECRET_KEY, algorithms=["HS256"])
            token_type = payload.get("type")
            if token_type not in (None, "access"):
                return None
            return payload
        except JWTError:
            return None

    def decode_refresh_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, settings.AUTH_SECRET_KEY, algorithms=["HS256"])
            if payload.get("type") != "refresh":
                return None
            return payload
        except JWTError:
            return None

    async def authenticate_user(self, db: AsyncSession, username: str, password: str) -> Optional[User]:
        user, status = await self.authenticate_user_with_status(db, username, password)
        if status != "ok":
            return None
        return user

    async def authenticate_user_with_status(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ) -> tuple[Optional[User], str]:
        user = await user_repository.get_by_username(db, username)
        if not user:
            return None, "invalid_credentials"
        if not user.is_active:
            return None, "inactive"

        now = datetime.utcnow()
        if user.locked_until and user.locked_until > now:
            return None, "locked"

        if not self.verify_password(password, user.password_hash):
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.AUTH_LOCK_MAX_ATTEMPTS:
                user.failed_login_attempts = 0
                user.locked_until = now + timedelta(minutes=settings.AUTH_LOCK_MINUTES)
                await db.flush()
                return None, "locked"
            await db.flush()
            return None, "invalid_credentials"

        if user.failed_login_attempts or user.locked_until:
            user.failed_login_attempts = 0
            user.locked_until = None
            await db.flush()
        return user, "ok"

    async def ensure_default_admin(self, db: AsyncSession) -> None:
        """初始化默认管理员（仅首次且配置了密码时创建）。"""
        default_admin_password = (settings.DEFAULT_ADMIN_PASSWORD or "").strip()
        if not default_admin_password:
            return

        existing = await user_repository.get_by_username(db, settings.DEFAULT_ADMIN_USERNAME)
        if existing:
            return

        await user_repository.create(
            db,
            {
                "username": settings.DEFAULT_ADMIN_USERNAME,
                "password_hash": self.hash_password(default_admin_password),
                "role": UserRole.ADMIN.value,
                "is_active": True,
            },
        )

    async def get_bootstrap_warnings(self, db: AsyncSession) -> list[str]:
        """返回首次部署常见配置告警（不阻断启动）。"""
        warnings: list[str] = []

        default_admin_password = (settings.DEFAULT_ADMIN_PASSWORD or "").strip()
        if not default_admin_password:
            user_count = await user_repository.count_all(db)
            if user_count == 0:
                warnings.append(
                    "未检测到任何用户且 DEFAULT_ADMIN_PASSWORD 为空：请先配置默认管理员密码并重启，避免无法登录。"
                )

        return warnings


auth_service = AuthService()
