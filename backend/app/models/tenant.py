"""
租户模型
"""
from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Tenant(Base):
    """租户表"""
    __tablename__ = "tenants"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    contact_name = Column(String(50))
    contact_phone = Column(String(20))
    contact_email = Column(String(100))
    address = Column(Text)
    status = Column(String(20), nullable=False, default="active")
    max_spaces = Column(Integer, nullable=False, default=100)
    max_users = Column(Integer, nullable=False, default=50)
    config_json = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime)

    # 关系
    users = relationship("User", back_populates="tenant", lazy="selectin")
    zones = relationship("ParkingZone", back_populates="tenant", lazy="selectin")
    spaces = relationship("ParkingSpace", back_populates="tenant", lazy="selectin")
    vehicles = relationship("Vehicle", back_populates="tenant", lazy="selectin")
    billing_accounts = relationship("BillingAccount", back_populates="tenant", lazy="selectin")

    def __repr__(self):
        return f"<Tenant(id={self.id}, code={self.code}, name={self.name})>"
