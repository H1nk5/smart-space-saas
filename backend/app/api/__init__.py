"""
API路由导出
"""
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.vehicles import router as vehicles_router
from app.api.spaces import router as spaces_router
from app.api.billing import router as billing_router
from app.api.audit import router as audit_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(vehicles_router, prefix="/vehicles", tags=["车辆管理"])
api_router.include_router(spaces_router, prefix="/spaces", tags=["车位管理"])
api_router.include_router(billing_router, prefix="/billing", tags=["计费管理"])
api_router.include_router(audit_router, prefix="/audit", tags=["审计日志"])
