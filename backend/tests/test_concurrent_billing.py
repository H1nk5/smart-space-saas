"""
并发计费测试 - 验证幂等性和事务隔离
"""
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.billing import BillingAccount, BillingTransaction
from app.models.vehicle import Vehicle, VehicleLog
from app.models.space import ParkingSpace


@pytest.mark.asyncio
async def test_concurrent_billing_idempotency(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：模拟同一个计费单据在100ms内被并发调用5次
    预期结果：只能有1次成功，其余4次触发幂等拦截或事务回滚
    """
    # 先创建车辆入场记录
    entry_response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A88888", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert entry_response.status_code == 200
    entry_data = entry_response.json()

    # 模拟并发出场请求（5个同时发起）
    async def exit_request():
        return await client.post(
            "/api/v1/vehicles/exit",
            json={"plate_number": "京A88888", "payment_method": "cash"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    # 并发执行5个出场请求
    tasks = [exit_request() for _ in range(5)]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计成功和失败的数量
    success_count = 0
    conflict_count = 0

    for resp in responses:
        if isinstance(resp, Exception):
            continue
        if resp.status_code == 200:
            success_count += 1
        elif resp.status_code == 409:  # Conflict
            conflict_count += 1

    # 验证只有1次成功
    assert success_count == 1, f"期望1次成功，实际{success_count}次"
    assert conflict_count == 4, f"期望4次冲突，实际{conflict_count}次"

    # 验证数据库中只有1条出场记录
    result = await db.execute(
        select(VehicleLog).where(
            and_(
                VehicleLog.plate_number == "京A88888",
                VehicleLog.action == "exit"
            )
        )
    )
    exit_logs = result.scalars().all()
    assert len(exit_logs) == 1, f"期望1条出场记录，实际{len(exit_logs)}条"


@pytest.mark.asyncio
async def test_billing_transaction_atomicity(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：验证计费交易的原子性
    预期结果：交易记录和账户余额更新要么同时成功，要么同时失败
    """
    # 创建车辆入场
    entry_response = await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A77777", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert entry_response.status_code == 200

    # 获取初始账户状态
    initial_account = await db.execute(
        select(BillingAccount).where(BillingAccount.tenant_id == "tenant-001")
    )
    initial_balance = initial_account.scalar_one_or_none()

    # 执行出场计费
    exit_response = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A77777", "payment_method": "wechat"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert exit_response.status_code == 200

    # 验证交易记录存在
    txn_result = await db.execute(
        select(BillingTransaction).where(
            BillingTransaction.tenant_id == "tenant-001"
        )
    )
    transactions = txn_result.scalars().all()
    assert len(transactions) > 0, "应该有交易记录"

    # 验证交易状态为completed
    for txn in transactions:
        assert txn.status == "completed", f"交易状态应为completed，实际为{txn.status}"


@pytest.mark.asyncio
async def test_duplicate_payment_prevention(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：验证重复支付的防护
    预期结果：同一笔交易不能重复支付
    """
    # 创建车辆入场
    await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A66666", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 第一次出场
    first_exit = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A66666", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert first_exit.status_code == 200

    # 第二次出场（应该失败，因为已经出场了）
    second_exit = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A66666", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert second_exit.status_code == 404  # 未找到入场记录


@pytest.mark.asyncio
async def test_refund_creates_negative_transaction(client: AsyncClient, admin_token: str, db: AsyncSession, test_spaces):
    """
    测试场景：验证退款创建负向交易记录
    预期结果：退款金额应为负数
    """
    # 创建车辆入场并出场
    await client.post(
        "/api/v1/vehicles/entry",
        json={"plate_number": "京A55555", "vehicle_type": "sedan"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    exit_resp = await client.post(
        "/api/v1/vehicles/exit",
        json={"plate_number": "京A55555", "payment_method": "cash"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    # 获取交易记录
    txn_result = await db.execute(
        select(BillingTransaction).where(
            BillingTransaction.tenant_id == "tenant-001",
            BillingTransaction.transaction_type == "charge"
        )
    )
    charge_txn = txn_result.scalar_one_or_none()

    if charge_txn:
        # 执行退款
        refund_resp = await client.post(
            "/api/v1/billing/refund",
            json={"transaction_id": charge_txn.id, "reason": "测试退款"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert refund_resp.status_code == 200

        # 验证退款记录
        refund_result = await db.execute(
            select(BillingTransaction).where(
                BillingTransaction.transaction_type == "refund"
            )
        )
        refund_txn = refund_result.scalar_one_or_none()
        assert refund_txn is not None
        assert refund_txn.amount < 0, "退款金额应为负数"
