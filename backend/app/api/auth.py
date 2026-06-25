"""
认证API
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user
)
from app.models.user import User
from app.models.tenant import Tenant
from app.services.audit_service import audit_service

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    tenant_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    tenant_id: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    tenant_code: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    phone: Optional[str]
    real_name: Optional[str]
    status: str
    tenant_id: str
    created_at: datetime


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    # 查找租户
    tenant_query = select(Tenant).where(Tenant.status == "active")
    if login_data.tenant_code:
        tenant_query = tenant_query.where(Tenant.code == login_data.tenant_code)

    result = await db.execute(tenant_query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租户不存在或已禁用",
        )

    # 查找用户
    result = await db.execute(
        select(User).where(
            and_(
                User.tenant_id == tenant.id,
                User.username == login_data.username,
                User.deleted_at.is_(None)
            )
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用",
        )

    # 更新最后登录时间
    user.last_login_at = datetime.utcnow()

    # 记录审计日志
    await audit_service.log(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        action="LOGIN",
        resource_type="user",
        resource_id=user.id,
        request=request,
        description=f"用户 {user.username} 登录系统"
    )

    # 生成Token
    access_token = create_access_token(
        data={"sub": user.id, "tenant_id": tenant.id, "username": user.username}
    )

    return LoginResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        tenant_id=tenant.id
    )


@router.post("/register", response_model=UserResponse)
async def register(
    request: Request,
    register_data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    # 查找租户
    result = await db.execute(
        select(Tenant).where(
            and_(
                Tenant.code == register_data.tenant_code,
                Tenant.status == "active"
            )
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="租户不存在或已禁用",
        )

    # 检查用户名是否已存在
    existing_user = await db.execute(
        select(User).where(
            and_(
                User.tenant_id == tenant.id,
                User.username == register_data.username
            )
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 创建用户
    user = User(
        tenant_id=tenant.id,
        username=register_data.username,
        password_hash=get_password_hash(register_data.password),
        email=register_data.email,
        phone=register_data.phone,
        real_name=register_data.real_name,
        status="active"
    )
    db.add(user)
    await db.flush()

    # 记录审计日志
    await audit_service.log_create(
        db=db,
        tenant_id=tenant.id,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        new_value={
            "username": user.username,
            "email": user.email,
            "phone": user.phone
        },
        request=request,
        description=f"新用户注册: {user.username}"
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        phone=user.phone,
        real_name=user.real_name,
        status=user.status,
        tenant_id=user.tenant_id,
        created_at=user.created_at
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户信息"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        phone=current_user.phone,
        real_name=current_user.real_name,
        status=current_user.status,
        tenant_id=current_user.tenant_id,
        created_at=current_user.created_at
    )
