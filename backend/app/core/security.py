"""
安全与认证模块 - JWT + 多租户隔离
"""
from datetime import datetime, timedelta
from typing import Optional, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole, RolePermission, Permission

# 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer Token
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """解码JWT Token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户（依赖注入）"""
    token = credentials.credentials
    payload = decode_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )

    # 查询用户
    result = await db.execute(
        select(User).where(
            and_(
                User.id == user_id,
                User.deleted_at.is_(None),
                User.status == "active"
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已禁用",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用",
        )
    return current_user


class TenantIsolation:
    """多租户隔离依赖"""

    def __init__(self, allow_cross_tenant: bool = False):
        self.allow_cross_tenant = allow_cross_tenant

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> str:
        """验证租户隔离"""
        # 从请求中获取tenant_id（路径参数或查询参数）
        tenant_id = request.path_params.get("tenant_id") or request.query_params.get("tenant_id")

        if not tenant_id:
            # 使用当前用户的tenant_id
            return current_user.tenant_id

        # 验证用户是否有权访问该租户
        if tenant_id != current_user.tenant_id and not self.allow_cross_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该租户的数据",
            )

        return tenant_id


class PermissionChecker:
    """权限检查器"""

    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """检查用户权限"""
        # 查询用户的所有权限
        result = await db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == current_user.id)
        )
        user_permissions = {row[0] for row in result.fetchall()}

        # 检查是否拥有所需权限
        missing_permissions = set(self.required_permissions) - user_permissions
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要: {', '.join(missing_permissions)}",
            )

        return current_user


# 常用权限检查器实例
require_space_read = PermissionChecker(["space:read"])
require_space_write = PermissionChecker(["space:write"])
require_vehicle_read = PermissionChecker(["vehicle:read"])
require_vehicle_write = PermissionChecker(["vehicle:write"])
require_vehicle_entry = PermissionChecker(["vehicle:entry"])
require_vehicle_exit = PermissionChecker(["vehicle:exit"])
require_billing_read = PermissionChecker(["billing:read"])
require_billing_write = PermissionChecker(["billing:write"])
require_audit_read = PermissionChecker(["audit:read"])
require_system_config = PermissionChecker(["system:config"])
