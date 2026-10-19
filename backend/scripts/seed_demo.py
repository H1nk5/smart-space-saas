"""Create an idempotent demonstration tenant for local evaluation."""

import asyncio
import os

from sqlalchemy import select

from app.core.database import get_db_context, init_db
from app.core.security import get_password_hash
from app.models.space import ParkingSpace, ParkingZone
from app.models.tenant import Tenant
from app.models.user import Permission, Role, RolePermission, User, UserRole


PERMISSIONS = (
    "space:read", "space:write", "vehicle:read", "vehicle:write",
    "vehicle:entry", "vehicle:exit", "vehicle:force_exit",
    "billing:read", "billing:write", "billing:payment", "billing:refund",
    "audit:read",
)


async def seed():
    await init_db()
    password = os.environ.get("DEMO_ADMIN_PASSWORD", "").strip()
    if len(password) < 10:
        raise SystemExit("DEMO_ADMIN_PASSWORD must contain at least 10 characters")

    async with get_db_context() as db:
        existing = await db.execute(select(Tenant).where(Tenant.code == "DEMO"))
        if existing.scalar_one_or_none():
            print("Demo tenant already exists; no changes made")
            return

        tenant = Tenant(name="星河智慧园区", code="DEMO", max_spaces=200, max_users=100)
        db.add(tenant)
        await db.flush()

        user = User(
            tenant_id=tenant.id,
            username="admin",
            password_hash=get_password_hash(password),
            real_name="演示管理员",
            status="active",
        )
        role = Role(tenant_id=tenant.id, name="admin", description="演示管理员", is_system=True)
        db.add_all([user, role])
        await db.flush()

        for code in PERMISSIONS:
            result = await db.execute(select(Permission).where(Permission.code == code))
            permission = result.scalar_one_or_none()
            if permission is None:
                permission = Permission(code=code, name=code, module=code.split(":", 1)[0])
                db.add(permission)
                await db.flush()
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        db.add(UserRole(user_id=user.id, role_id=role.id))

        zone = ParkingZone(
            tenant_id=tenant.id,
            name="A区",
            location="园区地面停车场",
            total_spaces=12,
            hourly_rate=500,
            daily_rate=3000,
        )
        db.add(zone)
        await db.flush()
        db.add_all([
            ParkingSpace(
                tenant_id=tenant.id,
                zone_id=zone.id,
                space_number=f"A-{index:03d}",
                space_type="ev_charging" if index in (1, 2) else "standard",
            )
            for index in range(1, 13)
        ])
    print("Demo tenant created: DEMO / admin")


if __name__ == "__main__":
    asyncio.run(seed())
