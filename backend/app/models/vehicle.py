"""
车辆与调度日志模型
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Vehicle(Base):
    """车辆表"""
    __tablename__ = "vehicles"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    plate_number = Column(String(20), nullable=False)
    vehicle_type = Column(String(20), nullable=False, default="sedan")
    owner_name = Column(String(50))
    owner_phone = Column(String(20))
    owner_user_id = Column(String(32), ForeignKey("users.id"))
    is_vip = Column(Boolean, nullable=False, default=False)
    vip_expire_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tenant = relationship("Tenant", back_populates="vehicles")
    owner = relationship("User", foreign_keys=[owner_user_id])
    logs = relationship("VehicleLog", back_populates="vehicle", lazy="selectin")

    def __repr__(self):
        return f"<Vehicle(id={self.id}, plate={self.plate_number})>"


class VehicleLog(Base):
    """车辆调度日志表 - 带乐观锁"""
    __tablename__ = "vehicle_logs"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    vehicle_id = Column(String(32), ForeignKey("vehicles.id"), nullable=False, index=True)
    space_id = Column(String(32), ForeignKey("parking_spaces.id"))
    action = Column(String(20), nullable=False)  # entry, exit, reserve, cancel_reserve
    plate_number = Column(String(20), nullable=False)
    entry_time = Column(DateTime)
    exit_time = Column(DateTime)
    duration_minutes = Column(Integer)
    fee_amount = Column(Integer, default=0)  # 分
    fee_status = Column(String(20), nullable=False, default="pending")
    operator_id = Column(String(32), ForeignKey("users.id"))
    gate_id = Column(String(50))
    snapshot_url = Column(Text)
    remark = Column(Text)
    idempotency_key = Column(String(64), unique=True)  # 幂等键
    version = Column(Integer, nullable=False, default=1)  # 乐观锁版本号
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    vehicle = relationship("Vehicle", back_populates="logs")
    space = relationship("ParkingSpace", foreign_keys=[space_id])
    operator = relationship("User", foreign_keys=[operator_id])

    def __repr__(self):
        return f"<VehicleLog(id={self.id}, action={self.action}, plate={self.plate_number})>"
