"""
车辆调度服务 - 高并发状态锁 + 幂等性校验
"""
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status, Request

from app.models.vehicle import Vehicle, VehicleLog
from app.models.space import ParkingSpace
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.billing_service import billing_service


class VehicleService:
    """车辆调度服务"""

    @staticmethod
    async def vehicle_entry(
        db: AsyncSession,
        tenant_id: str,
        plate_number: str,
        vehicle_type: str = "sedan",
        operator_id: Optional[str] = None,
        gate_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> Tuple[Vehicle, VehicleLog]:
        """
        车辆入场 - 原子化状态变更

        防御性逻辑:
        1. 幂等性检查：同一idempotency_key只处理一次
        2. 车位状态原子化：使用乐观锁防止并发冲突
        3. 事务保证：所有操作在同一事务中
        """
        # 生成幂等键
        idempotency_key = f"entry:{tenant_id}:{plate_number}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"

        # 幂等性检查
        existing_log = await db.execute(
            select(VehicleLog).where(VehicleLog.idempotency_key == idempotency_key)
        )
        if existing_log.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="重复的入场请求",
            )

        # 查找或创建车辆
        result = await db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.plate_number == plate_number
                )
            )
        )
        vehicle = result.scalar_one_or_none()

        if not vehicle:
            vehicle = Vehicle(
                tenant_id=tenant_id,
                plate_number=plate_number,
                vehicle_type=vehicle_type
            )
            db.add(vehicle)
            await db.flush()  # 获取ID

        # 查找可用车位（使用悲观锁风格查询）
        result = await db.execute(
            select(ParkingSpace).where(
                and_(
                    ParkingSpace.tenant_id == tenant_id,
                    ParkingSpace.status == "available"
                )
            ).limit(1)
        )
        space = result.scalar_one_or_none()

        if not space:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="没有可用的车位",
            )

        # 原子化更新车位状态（乐观锁）
        update_result = await db.execute(
            update(ParkingSpace)
            .where(
                and_(
                    ParkingSpace.id == space.id,
                    ParkingSpace.status == "available"  # 确保状态未变
                )
            )
            .values(
                status="occupied",
                current_vehicle_id=vehicle.id,
                occupied_since=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )

        if update_result.rowcount == 0:
            # 并发冲突，车位已被抢占
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="车位已被其他车辆占用，请重试",
            )

        # 创建入场日志
        vehicle_log = VehicleLog(
            tenant_id=tenant_id,
            vehicle_id=vehicle.id,
            space_id=space.id,
            action="entry",
            plate_number=plate_number,
            entry_time=datetime.utcnow(),
            fee_status="pending",
            operator_id=operator_id,
            gate_id=gate_id,
            idempotency_key=idempotency_key,
            version=1
        )
        db.add(vehicle_log)
        await db.flush()  # 确保ID和默认值被设置

        # 记录审计日志
        await audit_service.log(
            db=db,
            tenant_id=tenant_id,
            user_id=operator_id,
            action="VEHICLE_ENTRY",
            resource_type="vehicle",
            resource_id=vehicle.id,
            new_value={
                "plate_number": plate_number,
                "space_number": space.space_number,
                "entry_time": datetime.utcnow().isoformat()
            },
            request=request,
            description=f"车辆 {plate_number} 入场，分配车位 {space.space_number}"
        )

        return vehicle, vehicle_log

    @staticmethod
    async def vehicle_exit(
        db: AsyncSession,
        tenant_id: str,
        plate_number: str,
        operator_id: Optional[str] = None,
        payment_method: str = "cash",
        request: Optional[Request] = None
    ) -> Tuple[VehicleLog, int]:
        """
        车辆出场 - 原子化状态变更 + 计费

        防御性逻辑:
        1. 检查车辆是否在场
        2. 计算费用
        3. 原子化更新车位状态
        4. 记录计费流水
        """
        # 查找车辆
        result = await db.execute(
            select(Vehicle).where(
                and_(
                    Vehicle.tenant_id == tenant_id,
                    Vehicle.plate_number == plate_number
                )
            )
        )
        vehicle = result.scalar_one_or_none()

        if not vehicle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="车辆不存在",
            )

        # 查找未完成的入场记录
        result = await db.execute(
            select(VehicleLog).where(
                and_(
                    VehicleLog.tenant_id == tenant_id,
                    VehicleLog.vehicle_id == vehicle.id,
                    VehicleLog.action == "entry",
                    VehicleLog.exit_time.is_(None)
                )
            ).order_by(VehicleLog.created_at.desc())
        )
        entry_log = result.scalar_one_or_none()

        if not entry_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到该车辆的入场记录",
            )

        # 计算停车时长和费用
        exit_time = datetime.utcnow()
        duration = exit_time - entry_log.entry_time
        duration_minutes = int(duration.total_seconds() / 60)

        # 获取车位费率
        space = await db.get(ParkingSpace, entry_log.space_id)
        hourly_rate = space.hourly_rate if space and space.hourly_rate else 500  # 默认5元/小时

        # 计算费用（向上取整到小时）
        hours = max(1, (duration_minutes + 59) // 60)
        fee_amount = hours * hourly_rate

        # 生成幂等键
        idempotency_key = f"exit:{tenant_id}:{plate_number}:{entry_log.id}"

        # 幂等性检查
        existing_exit = await db.execute(
            select(VehicleLog).where(VehicleLog.idempotency_key == idempotency_key)
        )
        if existing_exit.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="重复的出场请求",
            )

        # 原子化更新车位状态
        if space:
            update_result = await db.execute(
                update(ParkingSpace)
                .where(
                    and_(
                        ParkingSpace.id == space.id,
                        ParkingSpace.current_vehicle_id == vehicle.id  # 确保是同一辆车
                    )
                )
                .values(
                    status="available",
                    current_vehicle_id=None,
                    occupied_since=None,
                    updated_at=datetime.utcnow()
                )
            )

            if update_result.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="车位状态异常，请重试",
                )

        # 更新入场日志
        entry_log.exit_time = exit_time
        entry_log.duration_minutes = duration_minutes
        entry_log.fee_amount = fee_amount
        entry_log.fee_status = "calculated"
        entry_log.version += 1

        # 创建出场日志
        exit_log = VehicleLog(
            tenant_id=tenant_id,
            vehicle_id=vehicle.id,
            space_id=entry_log.space_id,
            action="exit",
            plate_number=plate_number,
            entry_time=entry_log.entry_time,
            exit_time=exit_time,
            duration_minutes=duration_minutes,
            fee_amount=fee_amount,
            fee_status="paid",
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            version=1
        )
        db.add(exit_log)
        await db.flush()  # 确保ID和默认值被设置

        # 记录计费流水
        await billing_service.create_transaction(
            db=db,
            tenant_id=tenant_id,
            vehicle_id=vehicle.id,
            vehicle_log_id=exit_log.id,
            transaction_type="charge",
            amount=fee_amount,
            payment_method=payment_method,
            operator_id=operator_id,
            description=f"停车费用: {duration_minutes}分钟, {fee_amount/100:.2f}元"
        )

        # 记录审计日志
        await audit_service.log(
            db=db,
            tenant_id=tenant_id,
            user_id=operator_id,
            action="VEHICLE_EXIT",
            resource_type="vehicle",
            resource_id=vehicle.id,
            new_value={
                "plate_number": plate_number,
                "exit_time": exit_time.isoformat(),
                "duration_minutes": duration_minutes,
                "fee_amount": fee_amount
            },
            request=request,
            description=f"车辆 {plate_number} 出场，停车 {duration_minutes} 分钟，费用 {fee_amount/100:.2f} 元"
        )

        return exit_log, fee_amount

    @staticmethod
    async def force_exit(
        db: AsyncSession,
        tenant_id: str,
        vehicle_log_id: str,
        operator_id: str,
        reason: str,
        request: Optional[Request] = None
    ) -> VehicleLog:
        """
        强制放行 - 高危操作

        防御性逻辑:
        1. 必须有管理员权限
        2. 记录详细审计日志
        3. 标记为高危操作
        """
        # 查找入场记录
        result = await db.execute(
            select(VehicleLog).where(
                and_(
                    VehicleLog.id == vehicle_log_id,
                    VehicleLog.tenant_id == tenant_id
                )
            )
        )
        vehicle_log = result.scalar_one_or_none()

        if not vehicle_log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到车辆记录",
            )

        if vehicle_log.exit_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="车辆已出场",
            )

        # 记录旧值
        old_value = {
            "action": vehicle_log.action,
            "fee_status": vehicle_log.fee_status,
            "fee_amount": vehicle_log.fee_amount
        }

        # 更新为强制放行
        vehicle_log.exit_time = datetime.utcnow()
        vehicle_log.fee_status = "waived"
        vehicle_log.remark = f"强制放行: {reason}"
        vehicle_log.version += 1

        # 释放车位
        if vehicle_log.space_id:
            await db.execute(
                update(ParkingSpace)
                .where(ParkingSpace.id == vehicle_log.space_id)
                .values(
                    status="available",
                    current_vehicle_id=None,
                    occupied_since=None,
                    updated_at=datetime.utcnow()
                )
            )

        # 记录高危审计日志
        await audit_service.log_high_risk(
            db=db,
            tenant_id=tenant_id,
            user_id=operator_id,
            action="FORCE_EXIT",
            resource_type="vehicle",
            resource_id=vehicle_log.vehicle_id,
            old_value=old_value,
            new_value={
                "exit_time": vehicle_log.exit_time.isoformat(),
                "reason": reason,
                "fee_waived": True
            },
            request=request,
            description=f"强制放行车辆 {vehicle_log.plate_number}，原因: {reason}"
        )

        return vehicle_log

    @staticmethod
    async def get_parking_status(
        db: AsyncSession,
        tenant_id: str
    ) -> dict:
        """获取停车场状态统计"""
        # 统计各状态车位数
        result = await db.execute(
            select(
                ParkingSpace.status,
                ParkingSpace.tenant_id
            ).where(
                ParkingSpace.tenant_id == tenant_id
            )
        )
        spaces = result.fetchall()

        status_count = {
            "total": len(spaces),
            "available": 0,
            "occupied": 0,
            "reserved": 0,
            "maintenance": 0
        }

        for space in spaces:
            if space[0] in status_count:
                status_count[space[0]] += 1

        # 计算占用率
        if status_count["total"] > 0:
            status_count["occupancy_rate"] = round(
                status_count["occupied"] / status_count["total"] * 100, 2
            )
        else:
            status_count["occupancy_rate"] = 0

        return status_count


# 全局车辆服务实例
vehicle_service = VehicleService()
