"""
车辆管理API
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
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
from app.models.vehicle import Vehicle, VehicleLog
from app.services.vehicle_service import vehicle_service

router = APIRouter()


class VehicleEntryRequest(BaseModel):
    plate_number: str
    vehicle_type: str = "sedan"
    gate_id: Optional[str] = None


class VehicleExitRequest(BaseModel):
    plate_number: str
    payment_method: str = "cash"


class ForceExitRequest(BaseModel):
    vehicle_log_id: str
    reason: str


class VehicleResponse(BaseModel):
    id: str
    plate_number: str
    vehicle_type: str
    owner_name: Optional[str]
    owner_phone: Optional[str]
    is_vip: bool
    created_at: datetime


class VehicleLogResponse(BaseModel):
    id: str
    vehicle_id: str
    space_id: Optional[str]
    action: str
    plate_number: str
    entry_time: Optional[datetime]
    exit_time: Optional[datetime]
    duration_minutes: Optional[int]
    fee_amount: int
    fee_status: str
    created_at: datetime


class ParkingStatusResponse(BaseModel):
    total: int
    available: int
    occupied: int
    reserved: int
    maintenance: int
    occupancy_rate: float


@router.post("/entry", response_model=VehicleLogResponse)
async def vehicle_entry(
    request: Request,
    entry_data: VehicleEntryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["vehicle:entry"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """车辆入场"""
    vehicle, vehicle_log = await vehicle_service.vehicle_entry(
        db=db,
        tenant_id=tenant_id,
        plate_number=entry_data.plate_number,
        vehicle_type=entry_data.vehicle_type,
        operator_id=current_user.id,
        gate_id=entry_data.gate_id,
        request=request
    )

    return VehicleLogResponse(
        id=vehicle_log.id,
        vehicle_id=vehicle_log.vehicle_id,
        space_id=vehicle_log.space_id,
        action=vehicle_log.action,
        plate_number=vehicle_log.plate_number,
        entry_time=vehicle_log.entry_time,
        exit_time=vehicle_log.exit_time,
        duration_minutes=vehicle_log.duration_minutes,
        fee_amount=vehicle_log.fee_amount,
        fee_status=vehicle_log.fee_status,
        created_at=vehicle_log.created_at
    )


@router.post("/exit", response_model=VehicleLogResponse)
async def vehicle_exit(
    request: Request,
    exit_data: VehicleExitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["vehicle:exit"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """车辆出场"""
    vehicle_log, fee_amount = await vehicle_service.vehicle_exit(
        db=db,
        tenant_id=tenant_id,
        plate_number=exit_data.plate_number,
        operator_id=current_user.id,
        payment_method=exit_data.payment_method,
        request=request
    )

    return VehicleLogResponse(
        id=vehicle_log.id,
        vehicle_id=vehicle_log.vehicle_id,
        space_id=vehicle_log.space_id,
        action=vehicle_log.action,
        plate_number=vehicle_log.plate_number,
        entry_time=vehicle_log.entry_time,
        exit_time=vehicle_log.exit_time,
        duration_minutes=vehicle_log.duration_minutes,
        fee_amount=vehicle_log.fee_amount,
        fee_status=vehicle_log.fee_status,
        created_at=vehicle_log.created_at
    )


@router.post("/force-exit", response_model=VehicleLogResponse)
async def force_exit(
    request: Request,
    force_data: ForceExitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["vehicle:force_exit"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """强制放行（高危操作）"""
    vehicle_log = await vehicle_service.force_exit(
        db=db,
        tenant_id=tenant_id,
        vehicle_log_id=force_data.vehicle_log_id,
        operator_id=current_user.id,
        reason=force_data.reason,
        request=request
    )

    return VehicleLogResponse(
        id=vehicle_log.id,
        vehicle_id=vehicle_log.vehicle_id,
        space_id=vehicle_log.space_id,
        action=vehicle_log.action,
        plate_number=vehicle_log.plate_number,
        entry_time=vehicle_log.entry_time,
        exit_time=vehicle_log.exit_time,
        duration_minutes=vehicle_log.duration_minutes,
        fee_amount=vehicle_log.fee_amount,
        fee_status=vehicle_log.fee_status,
        created_at=vehicle_log.created_at
    )


@router.get("/status", response_model=ParkingStatusResponse)
async def get_parking_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["vehicle:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取停车场状态"""
    status_data = await vehicle_service.get_parking_status(db, tenant_id)
    return ParkingStatusResponse(**status_data)


@router.get("/logs", response_model=List[VehicleLogResponse])
async def get_vehicle_logs(
    plate_number: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["vehicle:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取车辆日志"""
    query = select(VehicleLog).where(VehicleLog.tenant_id == tenant_id)

    if plate_number:
        query = query.where(VehicleLog.plate_number == plate_number)
    if action:
        query = query.where(VehicleLog.action == action)
    if start_date:
        query = query.where(VehicleLog.created_at >= start_date)
    if end_date:
        query = query.where(VehicleLog.created_at <= end_date)

    query = query.order_by(VehicleLog.created_at.desc()).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        VehicleLogResponse(
            id=log.id,
            vehicle_id=log.vehicle_id,
            space_id=log.space_id,
            action=log.action,
            plate_number=log.plate_number,
            entry_time=log.entry_time,
            exit_time=log.exit_time,
            duration_minutes=log.duration_minutes,
            fee_amount=log.fee_amount,
            fee_status=log.fee_status,
            created_at=log.created_at
        )
        for log in logs
    ]
