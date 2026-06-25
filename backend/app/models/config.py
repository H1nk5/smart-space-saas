"""
系统配置模型
"""
from sqlalchemy import Column, String, Text, DateTime
from datetime import datetime
import uuid

from app.core.database import Base


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = "system_configs"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32))  # NULL表示全局配置
    key = Column(String(100), nullable=False)
    value = Column(Text)
    value_type = Column(String(20), nullable=False, default="string")
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig(key={self.key}, value={self.value})>"
