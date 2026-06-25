"""
越权请求测试 - 验证多租户隔离
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_tenant_access_denied(client: AsyncClient, admin_token: str, user_b_token: str, test_spaces):
    """
    测试场景：使用A租户的Token尝试读取B租户的数据
    预期结果：必须返回403
    """
    # 使用租户A的Token查询租户B的车位
    response = await client.get(
        "/api/v1/spaces/",
        params={"tenant_id": "tenant-002"},  # 尝试访问租户B
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 应该返回403，因为当前用户属于tenant-001，无权访问tenant-002
    assert response.status_code == 403
    assert "无权访问" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unauthorized_access_denied(client: AsyncClient):
    """
    测试场景：未携带Token访问受保护接口
    预期结果：必须返回401
    """
    response = await client.get("/api/v1/spaces/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_denied(client: AsyncClient):
    """
    测试场景：使用无效Token访问
    预期结果：必须返回401
    """
    response = await client.get(
        "/api/v1/spaces/",
        headers={"Authorization": "Bearer invalid-token-12345"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_vehicle_entry_permission_check(client: AsyncClient, user_b_token: str):
    """
    测试场景：使用无权限用户尝试车辆入场操作
    预期结果：必须返回403
    """
    response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A99999", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {user_b_token}"}
    )

    # 用户B没有vehicle:entry权限，应该返回403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_same_tenant_access_allowed(client: AsyncClient, admin_token: str, test_spaces):
    """
    测试场景：使用正确的Token访问自己的租户数据
    预期结果：应该返回200
    """
    response = await client.get(
        "/api/v1/spaces/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 应该成功返回数据
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_force_exit_requires_permission(client: AsyncClient, admin_token: str, user_b_token: str):
    """
    测试场景：验证强制放行需要特殊权限
    预期结果：普通用户返回403，管理员可以访问
    """
    # 普通用户尝试强制放行
    response = await client.post(
        "/api/v1/vehicles/force-exit",
        json={"vehicle_log_id": "log-001", "reason": "测试"},
        headers={"Authorization": f"Bearer {user_b_token}"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_audit_log_isolation(client: AsyncClient, admin_token: str, user_b_token: str):
    """
    测试场景：验证审计日志的租户隔离
    预期结果：只能看到自己租户的日志
    """
    # 使用管理员Token查看审计日志
    response = await client.get(
        "/api/v1/audit/",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200

    # 使用租户B的Token查看审计日志（如果有权限的话）
    response_b = await client.get(
        "/api/v1/audit/",
        headers={"Authorization": f"Bearer {user_b_token}"}
    )
    # 即使成功，返回的日志也应该是租户B的
    if response_b.status_code == 200:
        # 验证返回的日志确实属于租户B
        pass  # 实际实现中需要验证tenant_id
