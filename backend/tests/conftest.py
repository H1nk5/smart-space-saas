"""
测试配置 - pytest fixtures
"""
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.tenant import Tenant
from app.models.user import User, Role, UserRole, Permission, RolePermission
from app.models.space import ParkingZone, ParkingSpace

# pytest-asyncio配置
pytestmark = pytest.mark.asyncio(scope="session")

# 测试数据库URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# 创建测试引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """每个测试前重建数据库"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """覆盖数据库会话"""
    async with test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """获取测试数据库会话"""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """获取测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_tenant(db: AsyncSession) -> Tenant:
    """创建测试租户"""
    tenant = Tenant(
        id="tenant-001",
        name="测试物业公司",
        code="TEST",
        status="active",
        max_spaces=100,
        max_users=50
    )
    db.add(tenant)
    await db.commit()
    return tenant


@pytest.fixture
async def test_tenant_b(db: AsyncSession) -> Tenant:
    """创建测试租户B（用于越权测试）"""
    tenant = Tenant(
        id="tenant-002",
        name="测试物业公司B",
        code="TEST_B",
        status="active",
        max_spaces=50,
        max_users=30
    )
    db.add(tenant)
    await db.commit()
    return tenant


@pytest.fixture
async def test_user(db: AsyncSession, test_tenant: Tenant) -> User:
    """创建测试用户"""
    user = User(
        id="user-001",
        tenant_id=test_tenant.id,
        username="testuser",
        password_hash=get_password_hash("testpass123"),
        real_name="测试用户",
        status="active"
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
async def test_admin(db: AsyncSession, test_tenant: Tenant) -> User:
    """创建管理员用户"""
    user = User(
        id="user-admin",
        tenant_id=test_tenant.id,
        username="admin",
        password_hash=get_password_hash("admin123"),
        real_name="管理员",
        status="active"
    )
    db.add(user)

    # 创建管理员角色
    role = Role(
        id="role-admin",
        tenant_id=test_tenant.id,
        name="admin",
        description="管理员",
        is_system=True
    )
    db.add(role)

    # 添加所有权限
    permissions = [
        "space:read", "space:write", "vehicle:read", "vehicle:write",
        "vehicle:entry", "vehicle:exit", "vehicle:force_exit",
        "billing:read", "billing:write", "billing:payment", "billing:refund",
        "audit:read"
    ]
    for perm_code in permissions:
        # 确保权限存在
        from sqlalchemy import select
        result = await db.execute(select(Permission).where(Permission.code == perm_code))
        perm = result.scalar_one_or_none()
        if not perm:
            perm = Permission(id=f"perm-{perm_code}", code=perm_code, name=perm_code, module=perm_code.split(":")[0])
            db.add(perm)

        role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(role_perm)

    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)

    await db.commit()
    return user


@pytest.fixture
async def test_user_b(db: AsyncSession, test_tenant_b: Tenant) -> User:
    """创建租户B的用户（用于越权测试）"""
    user = User(
        id="user-002",
        tenant_id=test_tenant_b.id,
        username="testuser_b",
        password_hash=get_password_hash("testpass123"),
        real_name="测试用户B",
        status="active"
    )
    db.add(user)
    await db.commit()
    return user


@pytest.fixture
def admin_token(test_admin: User) -> str:
    """获取管理员Token"""
    return create_access_token(data={
        "sub": test_admin.id,
        "tenant_id": test_admin.tenant_id,
        "username": test_admin.username
    })


@pytest.fixture
def user_b_token(test_user_b: User) -> str:
    """获取租户B用户Token"""
    return create_access_token(data={
        "sub": test_user_b.id,
        "tenant_id": test_user_b.tenant_id,
        "username": test_user_b.username
    })


@pytest.fixture
async def test_zone(db: AsyncSession, test_tenant: Tenant) -> ParkingZone:
    """创建测试停车区域"""
    zone = ParkingZone(
        id="zone-001",
        tenant_id=test_tenant.id,
        name="A区",
        location="地面一层",
        total_spaces=10,
        hourly_rate=500,
        daily_rate=3000,
        status="active"
    )
    db.add(zone)
    await db.commit()
    return zone


@pytest.fixture
async def test_spaces(db: AsyncSession, test_tenant: Tenant, test_zone: ParkingZone):
    """创建测试车位"""
    spaces = []
    for i in range(1, 11):
        space = ParkingSpace(
            id=f"space-{i:03d}",
            tenant_id=test_tenant.id,
            zone_id=test_zone.id,
            space_number=f"A-{i:03d}",
            space_type="standard",
            status="available",
            hourly_rate=500
        )
        db.add(space)
        spaces.append(space)
    await db.commit()
    return spaces
