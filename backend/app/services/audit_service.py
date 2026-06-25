"""
审计日志服务 - 自动拦截高危操作
"""
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request

from app.models.audit import AuditLog
from app.models.user import User


class AuditService:
    """审计日志服务"""

    # 高危操作类型
    HIGH_RISK_ACTIONS = {
        "FORCE_EXIT",           # 强制放行
        "DELETE",               # 删除操作
        "ROLE_CHANGE",          # 角色变更
        "PERMISSION_CHANGE",    # 权限变更
        "PASSWORD_CHANGE",      # 密码修改
        "USER_LOCK",            # 用户锁定
        "REFUND",               # 退款
        "FEE_ADJUSTMENT",       # 费用调整
        "CONFIG_CHANGE",        # 配置变更
        "BATCH_DELETE",         # 批量删除
    }

    @staticmethod
    async def log(
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        request: Optional[Request] = None,
        severity: str = "info",
        description: Optional[str] = None
    ) -> AuditLog:
        """记录审计日志"""
        # 序列化变更值
        old_json = json.dumps(old_value, ensure_ascii=False, default=str) if old_value else None
        new_json = json.dumps(new_value, ensure_ascii=False, default=str) if new_value else None

        # 获取请求信息
        ip_address = None
        user_agent = None
        request_id = None

        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            request_id = request.headers.get("x-request-id")

        # 根据操作类型自动判断严重级别
        if action in AuditService.HIGH_RISK_ACTIONS:
            severity = "critical"

        # 创建审计日志
        audit_log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_json,
            new_value=new_json,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            severity=severity,
            description=description
        )

        db.add(audit_log)
        # 注意：不在这里commit，由调用方的事务统一提交

        return audit_log

    @staticmethod
    async def log_create(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        new_value: Any,
        request: Optional[Request] = None,
        description: Optional[str] = None
    ) -> AuditLog:
        """记录创建操作"""
        return await AuditService.log(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="CREATE",
            resource_type=resource_type,
            resource_id=resource_id,
            new_value=new_value,
            request=request,
            description=description or f"创建{resource_type}: {resource_id}"
        )

    @staticmethod
    async def log_update(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        old_value: Any,
        new_value: Any,
        request: Optional[Request] = None,
        description: Optional[str] = None
    ) -> AuditLog:
        """记录更新操作"""
        return await AuditService.log(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="UPDATE",
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            request=request,
            description=description or f"更新{resource_type}: {resource_id}"
        )

    @staticmethod
    async def log_delete(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        old_value: Any = None,
        request: Optional[Request] = None,
        description: Optional[str] = None
    ) -> AuditLog:
        """记录删除操作"""
        return await AuditService.log(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="DELETE",
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            request=request,
            severity="critical",
            description=description or f"删除{resource_type}: {resource_id}"
        )

    @staticmethod
    async def log_high_risk(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        request: Optional[Request] = None,
        description: Optional[str] = None
    ) -> AuditLog:
        """记录高危操作"""
        return await AuditService.log(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            request=request,
            severity="critical",
            description=description
        )

    @staticmethod
    async def get_recent_logs(
        db: AsyncSession,
        tenant_id: str,
        limit: int = 50,
        severity: Optional[str] = None,
        resource_type: Optional[str] = None
    ) -> list:
        """获取最近的审计日志"""
        query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

        if severity:
            query = query.where(AuditLog.severity == severity)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()


# 全局审计服务实例
audit_service = AuditService()
