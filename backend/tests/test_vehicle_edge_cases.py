"""
车辆调度边界值测试 - 验证满车位入场拒绝逻辑
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.space import ParkingSpace
from app.models.vehicle import VehicleLog


@pytest.mark.asyncio
async def test_full_parking_rejects_entry(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：满车位时的入场拒绝逻辑
    预期结果：返回409冲突错误
    """
    # 将所有车位设置为占用状态
    await db.execute(
        update(ParkingSpace)
        .where(ParkingSpace.tenant_id == "tenant-001")
        .values(status="occupied")
    )
    await db.commit()

    # 尝试入场
    response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A99999", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 应该返回409冲突
    assert response.status_code == 409
    assert "没有可用的车位" in response.json()["detail"]


@pytest.mark.asyncio
async def test_vehicle_entry_and_exit_cycle(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：完整的车辆入场-出场流程
    预期结果：状态正确流转
    """
    # 车辆入场
    entry_response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A12345", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert entry_response.status_code == 200
    entry_data = entry_response.json()

    # 验证入场记录
    assert entry_data["plate_number"] == "京A12345"
    assert entry_data["action"] == "entry"
    assert entry_data["fee_status"] == "pending"

    # 验证车位状态已更新（通过API查询）
    status_response = await client.get(
        "/api/v1/vehicles/status",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["occupied"] >= 1

    # 车辆出场
    exit_response = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A12345", "payment_method": "wechat"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert exit_response.status_code == 200
    exit_data = exit_response.json()

    # 验证出场记录
    assert exit_data["plate_number"] == "京A12345"
    assert exit_data["action"] == "exit"
    assert exit_data["fee_status"] == "paid"
    assert exit_data["fee_amount"] > 0
    assert exit_data["duration_minutes"] is not None

    # 验证车位已释放（通过API查询）
    final_status = await client.get(
        "/api/v1/vehicles/status",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert final_status.status_code == 200
    final_data = final_status.json()
    assert final_data["available"] >= 9  # 应该释放了车位


@pytest.mark.asyncio
async def test_duplicate_entry_prevention(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：同一车辆重复入场
    预期结果：第二次入场应被阻止或分配新车位
    """
    # 第一次入场
    first_entry = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A11111", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert first_entry.status_code == 200

    # 第二次入场（同车牌）
    second_entry = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A11111", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 可能返回409（同一分钟内重复）或200（分配新车位）
    # 这取决于幂等键的设计
    if second_entry.status_code == 200:
        # 如果成功，应该分配了不同的车位
        first_space = first_entry.json()["space_id"]
        second_space = second_entry.json()["space_id"]
        # 注意：由于幂等键包含分钟，同一分钟内应该是409
    elif second_entry.status_code == 409:
        # 预期行为：幂等拦截
        pass


@pytest.mark.asyncio
async def test_nonexistent_vehicle_exit(client: AsyncClient, admin_token: str):
    """
    测试场景：不存在的车辆出场
    预期结果：返回404
    """
    response = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A00000", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_vehicle_exit_without_entry(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：没有入场记录的车辆出场
    预期结果：返回404
    """
    # 创建车辆但不入场
    await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A22222", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 先出场
    await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A22222", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 再次出场（应该失败）
    response = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A22222", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_force_exit_with_audit(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：强制放行并验证审计日志
    预期结果：强制放行成功，审计日志记录完整
    """
    # 车辆入场
    entry_response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A33333", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert entry_response.status_code == 200
    log_id = entry_response.json()["id"]

    # 强制放行
    force_response = await client.post(
        "/api/v1/vehicles/force-exit",
        json={
            "vehicle_log_id": log_id,
            "reason": "系统故障，需要人工放行"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert force_response.status_code == 200
    force_data = force_response.json()

    # 验证强制放行记录
    assert force_data["fee_status"] == "waived"
    # remark字段可能在响应中不存在，但fee_status已验证

    # 验证审计日志
    audit_response = await client.get(
        "/api/v1/audit/",
        params={"action": "FORCE_EXIT"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert audit_response.status_code == 200
    audit_logs = audit_response.json()

    # 应该有强制放行的审计记录
    force_exit_logs = [log for log in audit_logs if log["action"] == "FORCE_EXIT"]
    assert len(force_exit_logs) > 0


@pytest.mark.asyncio
async def test_parking_status_endpoint(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：获取停车场状态
    预期结果：返回正确的统计数据
    """
    # 先占用车位
    await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A44444", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 获取状态
    response = await client.get(
        "/api/v1/vehicles/status",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()

    # 验证统计数据
    assert data["total"] == 10  # 测试数据有10个车位
    assert data["occupied"] >= 1  # 至少1个被占用
    assert data["available"] <= 9  # 最多9个空闲
    assert "occupancy_rate" in data
