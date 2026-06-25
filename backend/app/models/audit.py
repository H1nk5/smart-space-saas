"""
审计日志模型 - 不可篡改的操作记录
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(32), ForeignKey("users.id"))
    action = Column(String(30), nullable=False)
    resource_type = Column(String(30), nullable=False)
    resource_id = Column(String(32))
    old_value = Column(Text)  # JSON
    new_value = Column(Text)  # JSON
    ip_address = Column(String(50))
    user_agent = Column(Text)
    request_id = Column(String(64))
    severity = Column(String(20), nullable=False, default="info")
    description = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource_type})>"
