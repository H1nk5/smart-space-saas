"""
车位管理API
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import (
    get_current_active_user,
    TenantIsolation,
    PermissionChecker
)
from app.models.user import User
from app.models.space import ParkingZone, ParkingSpace
from app.services.audit_service import audit_service

router = APIRouter()


class ZoneCreateRequest(BaseModel):
    name: str
    location: Optional[str] = None
    total_spaces: int = 0
    hourly_rate: int = 500
    daily_rate: int = 3000
    monthly_rate: int = 30000


class ZoneResponse(BaseModel):
    id: str
    name: str
    location: Optional[str]
    total_spaces: int
    hourly_rate: int
    daily_rate: int
    monthly_rate: int
    status: str
    created_at: datetime


class SpaceCreateRequest(BaseModel):
    zone_id: str
    space_number: str
    space_type: str = "standard"
    hourly_rate: Optional[int] = None


class SpaceResponse(BaseModel):
    id: str
    zone_id: str
    space_number: str
    space_type: str
    status: str
    current_vehicle_id: Optional[str]
    occupied_since: Optional[datetime]
    hourly_rate: Optional[int]
    created_at: datetime


class SpaceUpdateRequest(BaseModel):
    space_type: Optional[str] = None
    status: Optional[str] = None
    hourly_rate: Optional[int] = None


@router.post("/zones", response_model=ZoneResponse)
async def create_zone(
    request: Request,
    zone_data: ZoneCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["space:write"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """创建停车区域"""
    zone = ParkingZone(
        tenant_id=tenant_id,
        name=zone_data.name,
        location=zone_data.location,
        total_spaces=zone_data.total_spaces,
        hourly_rate=zone_data.hourly_rate,
        daily_rate=zone_data.daily_rate,
        monthly_rate=zone_data.monthly_rate,
        status="active"
    )
    db.add(zone)
    await db.flush()

    # 记录审计日志
    await audit_service.log_create(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        resource_type="parking_zone",
        resource_id=zone.id,
        new_value={
            "name": zone.name,
            "location": zone.location,
            "total_spaces": zone.total_spaces
        },
        request=request,
        description=f"创建停车区域: {zone.name}"
    )

    return ZoneResponse(
        id=zone.id,
        name=zone.name,
        location=zone.location,
        total_spaces=zone.total_spaces,
        hourly_rate=zone.hourly_rate,
        daily_rate=zone.daily_rate,
        monthly_rate=zone.monthly_rate,
        status=zone.status,
        created_at=zone.created_at
    )


@router.get("/zones", response_model=List[ZoneResponse])
async def get_zones(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["space:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取所有停车区域"""
    result = await db.execute(
        select(ParkingZone).where(ParkingZone.tenant_id == tenant_id)
    )
    zones = result.scalars().all()

    return [
        ZoneResponse(
            id=zone.id,
            name=zone.name,
            location=zone.location,
            total_spaces=zone.total_spaces,
            hourly_rate=zone.hourly_rate,
            daily_rate=zone.daily_rate,
            monthly_rate=zone.monthly_rate,
            status=zone.status,
            created_at=zone.created_at
        )
        for zone in zones
    ]


@router.post("/", response_model=SpaceResponse)
async def create_space(
    request: Request,
    space_data: SpaceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["space:write"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """创建车位"""
    # 验证区域存在
    zone = await db.get(ParkingZone, space_data.zone_id)
    if not zone or zone.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="停车区域不存在",
        )

    # 检查车位编号是否重复
    existing_space = await db.execute(
        select(ParkingSpace).where(
            and_(
                ParkingSpace.tenant_id == tenant_id,
                ParkingSpace.space_number == space_data.space_number
            )
        )
    )
    if existing_space.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="车位编号已存在",
        )

    space = ParkingSpace(
        tenant_id=tenant_id,
        zone_id=space_data.zone_id,
        space_number=space_data.space_number,
        space_type=space_data.space_type,
        status="available",
        hourly_rate=space_data.hourly_rate
    )
    db.add(space)
    await db.flush()

    # 记录审计日志
    await audit_service.log_create(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        resource_type="parking_space",
        resource_id=space.id,
        new_value={
            "space_number": space.space_number,
            "zone_id": space.zone_id,
            "space_type": space.space_type
        },
        request=request,
        description=f"创建车位: {space.space_number}"
    )

    return SpaceResponse(
        id=space.id,
        zone_id=space.zone_id,
        space_number=space.space_number,
        space_type=space.space_type,
        status=space.status,
        current_vehicle_id=space.current_vehicle_id,
        occupied_since=space.occupied_since,
        hourly_rate=space.hourly_rate,
        created_at=space.created_at
    )


@router.get("/", response_model=List[SpaceResponse])
async def get_spaces(
    zone_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    space_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["space:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取车位列表"""
    query = select(ParkingSpace).where(ParkingSpace.tenant_id == tenant_id)

    if zone_id:
        query = query.where(ParkingSpace.zone_id == zone_id)
    if status_filter:
        query = query.where(ParkingSpace.status == status_filter)
    if space_type:
        query = query.where(ParkingSpace.space_type == space_type)

    result = await db.execute(query)
    spaces = result.scalars().all()

    return [
        SpaceResponse(
            id=space.id,
            zone_id=space.zone_id,
            space_number=space.space_number,
            space_type=space.space_type,
            status=space.status,
            current_vehicle_id=space.current_vehicle_id,
            occupied_since=space.occupied_since,
            hourly_rate=space.hourly_rate,
            created_at=space.created_at
        )
        for space in spaces
    ]


@router.put("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: str,
    request: Request,
    update_data: SpaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["space:write"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """更新车位信息"""
    result = await db.execute(
        select(ParkingSpace).where(
            and_(
                ParkingSpace.id == space_id,
                ParkingSpace.tenant_id == tenant_id
            )
        )
    )
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="车位不存在",
        )

    # 记录旧值
    old_value = {
        "space_type": space.space_type,
        "status": space.status,
        "hourly_rate": space.hourly_rate
    }

    # 更新字段
    if update_data.space_type is not None:
        space.space_type = update_data.space_type
    if update_data.status is not None:
        space.status = update_data.status
    if update_data.hourly_rate is not None:
        space.hourly_rate = update_data.hourly_rate

    space.updated_at = datetime.utcnow()

    # 记录审计日志
    new_value = {
        "space_type": space.space_type,
        "status": space.status,
        "hourly_rate": space.hourly_rate
    }
    await audit_service.log_update(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        resource_type="parking_space",
        resource_id=space.id,
        old_value=old_value,
        new_value=new_value,
        request=request,
        description=f"更新车位: {space.space_number}"
    )

    return SpaceResponse(
        id=space.id,
        zone_id=space.zone_id,
        space_number=space.space_number,
        space_type=space.space_type,
        status=space.status,
        current_vehicle_id=space.current_vehicle_id,
        occupied_since=space.occupied_since,
        hourly_rate=space.hourly_rate,
        created_at=space.created_at
    )
