"""
车位空间模型
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class ParkingZone(Base):
    """停车区域表"""
    __tablename__ = "parking_zones"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    location = Column(Text)
    total_spaces = Column(Integer, nullable=False, default=0)
    hourly_rate = Column(Integer, nullable=False, default=500)  # 分/小时
    daily_rate = Column(Integer, nullable=False, default=3000)  # 分/天
    monthly_rate = Column(Integer, nullable=False, default=30000)  # 分/月
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tenant = relationship("Tenant", back_populates="zones")
    spaces = relationship("ParkingSpace", back_populates="zone", lazy="selectin")

    def __repr__(self):
        return f"<ParkingZone(id={self.id}, name={self.name})>"


class ParkingSpace(Base):
    """车位表"""
    __tablename__ = "parking_spaces"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    zone_id = Column(String(32), ForeignKey("parking_zones.id"), nullable=False, index=True)
    space_number = Column(String(20), nullable=False)
    space_type = Column(String(20), nullable=False, default="standard")
    status = Column(String(20), nullable=False, default="available")
    current_vehicle_id = Column(String(32), ForeignKey("vehicles.id"), index=True)
    occupied_since = Column(DateTime)
    reserved_by = Column(String(32), ForeignKey("users.id"))
    reserved_until = Column(DateTime)
    hourly_rate = Column(Integer)  # 覆盖区域默认费率
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tenant = relationship("Tenant", back_populates="spaces")
    zone = relationship("ParkingZone", back_populates="spaces")
    current_vehicle = relationship("Vehicle", foreign_keys=[current_vehicle_id])

    def __repr__(self):
        return f"<ParkingSpace(id={self.id}, number={self.space_number}, status={self.status})>"
