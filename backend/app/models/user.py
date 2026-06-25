"""
用户与权限模型
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100))
    phone = Column(String(20))
    password_hash = Column(String(128), nullable=False)
    real_name = Column(String(50))
    avatar_url = Column(Text)
    status = Column(String(20), nullable=False, default="active")
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime)

    # 关系
    tenant = relationship("Tenant", back_populates="users")
    roles = relationship("Role", secondary="user_roles", back_populates="users", lazy="selectin")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class Role(Base):
    """角色表"""
    __tablename__ = "roles"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    tenant_id = Column(String(32), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    description = Column(Text)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关系
    users = relationship("User", secondary="user_roles", back_populates="roles", lazy="selectin")
    permissions = relationship("Permission", secondary="role_permissions", back_populates="roles", lazy="selectin")

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class Permission(Base):
    """权限表"""
    __tablename__ = "permissions"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(50), nullable=False)
    module = Column(String(30), nullable=False)
    description = Column(Text)

    # 关系
    roles = relationship("Role", secondary="role_permissions", back_populates="permissions", lazy="selectin")

    def __repr__(self):
        return f"<Permission(code={self.code}, name={self.name})>"


class UserRole(Base):
    """用户角色关联表"""
    __tablename__ = "user_roles"

    user_id = Column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(String(32), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by = Column(String(32))


class RolePermission(Base):
    """角色权限关联表"""
    __tablename__ = "role_permissions"

    role_id = Column(String(32), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(String(32), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
