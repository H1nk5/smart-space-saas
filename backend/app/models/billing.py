"""
计费与账单模型
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class BillingAccount(Base):
    """计费账户表"""
    __tablename__ = "billing_accounts"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(String(32), ForeignKey("users.id"))
    vehicle_id = Column(String(32), ForeignKey("vehicles.id"))
    account_type = Column(String(20), nullable=False, default="individual")
    balance = Column(Integer, nullable=False, default=0)  # 分
    credit_limit = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    tenant = relationship("Tenant", back_populates="billing_accounts")
    user = relationship("User", foreign_keys=[user_id])
    vehicle = relationship("Vehicle", foreign_keys=[vehicle_id])
    transactions = relationship("BillingTransaction", back_populates="account", lazy="selectin")

    def __repr__(self):
        return f"<BillingAccount(id={self.id}, balance={self.balance})>"


class BillingTransaction(Base):
    """账单流水表 - 带幂等键"""
    __tablename__ = "billing_transactions"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    account_id = Column(String(32), ForeignKey("billing_accounts.id"), nullable=False, index=True)
    vehicle_log_id = Column(String(32), ForeignKey("vehicle_logs.id"))
    transaction_type = Column(String(20), nullable=False)  # charge, payment, refund, adjustment, subscription
    amount = Column(Integer, nullable=False)  # 分
    balance_after = Column(Integer, nullable=False)  # 分
    description = Column(Text)
    payment_method = Column(String(20))
    payment_reference = Column(String(100))
    status = Column(String(20), nullable=False, default="pending")
    operator_id = Column(String(32), ForeignKey("users.id"))
    idempotency_key = Column(String(64), unique=True)  # 幂等键
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # 关系
    account = relationship("BillingAccount", back_populates="transactions")
    vehicle_log = relationship("VehicleLog", foreign_keys=[vehicle_log_id])
    operator = relationship("User", foreign_keys=[operator_id])

    def __repr__(self):
        return f"<BillingTransaction(id={self.id}, type={self.transaction_type}, amount={self.amount})>"
