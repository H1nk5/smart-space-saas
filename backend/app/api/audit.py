"""
审计日志API
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import (
    get_current_active_user,
    TenantIsolation,
    PermissionChecker
)
from app.models.user import User
from app.models.audit import AuditLog
from app.services.audit_service import audit_service

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    ip_address: Optional[str]
    severity: str
    description: Optional[str]
    created_at: datetime


class AuditLogFilter(BaseModel):
    action: Optional[str] = None
    resource_type: Optional[str] = None
    severity: Optional[str] = None
    user_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@router.get("/", response_model=List[AuditLogResponse])
async def get_audit_logs(
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["audit:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取审计日志"""
    query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if severity:
        query = query.where(AuditLog.severity == severity)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    query = query.order_by(AuditLog.created_at.desc()).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            old_value=log.old_value,
            new_value=log.new_value,
            ip_address=log.ip_address,
            severity=log.severity,
            description=log.description,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/high-risk", response_model=List[AuditLogResponse])
async def get_high_risk_logs(
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["audit:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取高危操作日志"""
    logs = await audit_service.get_recent_logs(
        db=db,
        tenant_id=tenant_id,
        limit=limit,
        severity="critical"
    )

    return [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            old_value=log.old_value,
            new_value=log.new_value,
            ip_address=log.ip_address,
            severity=log.severity,
            description=log.description,
            created_at=log.created_at
        )
        for log in logs
    ]


@router.get("/stats")
async def get_audit_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["audit:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取审计日志统计"""
    from sqlalchemy import func

    query = select(
        AuditLog.severity,
        func.count(AuditLog.id).label("count")
    ).where(AuditLog.tenant_id == tenant_id)

    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)

    query = query.group_by(AuditLog.severity)

    result = await db.execute(query)
    stats = result.fetchall()

    # 获取总操作数
    total_query = select(func.count(AuditLog.id)).where(AuditLog.tenant_id == tenant_id)
    if start_date:
        total_query = total_query.where(AuditLog.created_at >= start_date)
    if end_date:
        total_query = total_query.where(AuditLog.created_at <= end_date)

    total_result = await db.execute(total_query)
    total = total_result.scalar()

    # 获取最近的高危操作
    recent_high_risk = await audit_service.get_recent_logs(
        db=db,
        tenant_id=tenant_id,
        limit=5,
        severity="critical"
    )

    return {
        "total_operations": total,
        "by_severity": {row[0]: row[1] for row in stats},
        "recent_high_risk": [
            {
                "action": log.action,
                "resource_type": log.resource_type,
                "description": log.description,
                "created_at": log.created_at.isoformat()
            }
            for log in recent_high_risk
        ]
    }
