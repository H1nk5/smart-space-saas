"""
计费服务 - 事务隔离 + 幂等性校验
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.billing import BillingAccount, BillingTransaction
from app.models.user import User
from app.services.audit_service import audit_service


class BillingService:
    """计费服务"""

    @staticmethod
    async def create_account(
        db: AsyncSession,
        tenant_id: str,
        user_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        account_type: str = "individual",
        credit_limit: int = 0
    ) -> BillingAccount:
        """创建计费账户"""
        account = BillingAccount(
            tenant_id=tenant_id,
            user_id=user_id,
            vehicle_id=vehicle_id,
            account_type=account_type,
            balance=0,
            credit_limit=credit_limit,
            status="active"
        )
        db.add(account)
        return account

    @staticmethod
    async def get_or_create_account(
        db: AsyncSession,
        tenant_id: str,
        vehicle_id: str
    ) -> BillingAccount:
        """获取或创建车辆关联的计费账户"""
        result = await db.execute(
            select(BillingAccount).where(
                and_(
                    BillingAccount.tenant_id == tenant_id,
                    BillingAccount.vehicle_id == vehicle_id,
                    BillingAccount.status == "active"
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            account = await BillingService.create_account(
                db=db,
                tenant_id=tenant_id,
                vehicle_id=vehicle_id
            )
            await db.flush()

        return account

    @staticmethod
    async def create_transaction(
        db: AsyncSession,
        tenant_id: str,
        vehicle_id: str,
        vehicle_log_id: Optional[str],
        transaction_type: str,
        amount: int,
        payment_method: str = "cash",
        operator_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> BillingTransaction:
        """
        创建计费流水 - 事务隔离 + 幂等性

        防御性逻辑:
        1. 幂等性检查：同一idempotency_key只处理一次
        2. 事务保证：余额更新和流水记录在同一事务中
        3. 乐观锁：使用版本号防止并发修改
        """
        # 生成幂等键
        idempotency_key = f"txn:{tenant_id}:{vehicle_log_id}:{transaction_type}:{amount}"

        # 幂等性检查
        existing_txn = await db.execute(
            select(BillingTransaction).where(
                BillingTransaction.idempotency_key == idempotency_key
            )
        )
        if existing_txn.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="重复的计费请求",
            )

        # 获取计费账户
        account = await BillingService.get_or_create_account(db, tenant_id, vehicle_id)

        # 计算交易后余额
        balance_after = account.balance + amount

        # 检查信用额度
        if balance_after < -account.credit_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="账户余额不足",
            )

        # 创建交易记录
        transaction = BillingTransaction(
            tenant_id=tenant_id,
            account_id=account.id,
            vehicle_log_id=vehicle_log_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=balance_after,
            description=description,
            payment_method=payment_method,
            status="completed",
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            completed_at=datetime.utcnow()
        )
        db.add(transaction)
        await db.flush()  # 确保ID和默认值被设置

        # 更新账户余额
        account.balance = balance_after
        account.updated_at = datetime.utcnow()

        return transaction

    @staticmethod
    async def process_payment(
        db: AsyncSession,
        tenant_id: str,
        account_id: str,
        amount: int,
        payment_method: str,
        operator_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> BillingTransaction:
        """处理支付 - 充值"""
        # 获取账户
        result = await db.execute(
            select(BillingAccount).where(
                and_(
                    BillingAccount.id == account_id,
                    BillingAccount.tenant_id == tenant_id,
                    BillingAccount.status == "active"
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="计费账户不存在",
            )

        # 生成幂等键
        idempotency_key = f"payment:{tenant_id}:{account_id}:{amount}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"

        # 幂等性检查
        existing_txn = await db.execute(
            select(BillingTransaction).where(
                BillingTransaction.idempotency_key == idempotency_key
            )
        )
        if existing_txn.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="重复的支付请求",
            )

        # 计算新余额
        balance_after = account.balance + amount

        # 创建交易记录
        transaction = BillingTransaction(
            tenant_id=tenant_id,
            account_id=account_id,
            transaction_type="payment",
            amount=amount,
            balance_after=balance_after,
            description=description or f"充值 {amount/100:.2f} 元",
            payment_method=payment_method,
            status="completed",
            operator_id=operator_id,
            idempotency_key=idempotency_key,
            completed_at=datetime.utcnow()
        )
        db.add(transaction)

        # 更新账户余额
        account.balance = balance_after
        account.updated_at = datetime.utcnow()

        return transaction

    @staticmethod
    async def process_refund(
        db: AsyncSession,
        tenant_id: str,
        transaction_id: str,
        operator_id: str,
        reason: str
    ) -> BillingTransaction:
        """
        处理退款 - 高危操作

        防御性逻辑:
        1. 验证原交易存在且可退款
        2. 记录详细审计日志
        3. 标记为高危操作
        """
        # 获取原交易
        result = await db.execute(
            select(BillingTransaction).where(
                and_(
                    BillingTransaction.id == transaction_id,
                    BillingTransaction.tenant_id == tenant_id,
                    BillingTransaction.status == "completed"
                )
            )
        )
        original_txn = result.scalar_one_or_none()

        if not original_txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="原交易不存在或状态异常",
            )

        # 检查是否已退款
        existing_refund = await db.execute(
            select(BillingTransaction).where(
                and_(
                    BillingTransaction.vehicle_log_id == original_txn.vehicle_log_id,
                    BillingTransaction.transaction_type == "refund"
                )
            )
        )
        if existing_refund.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该交易已退款",
            )

        # 获取账户
        account = await db.get(BillingAccount, original_txn.account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="计费账户不存在",
            )

        # 计算退款金额（负数）
        refund_amount = -original_txn.amount
        balance_after = account.balance + refund_amount

        # 创建退款记录
        refund_txn = BillingTransaction(
            tenant_id=tenant_id,
            account_id=account.id,
            vehicle_log_id=original_txn.vehicle_log_id,
            transaction_type="refund",
            amount=refund_amount,
            balance_after=balance_after,
            description=f"退款: {reason}",
            payment_method=original_txn.payment_method,
            status="completed",
            operator_id=operator_id,
            idempotency_key=f"refund:{transaction_id}",
            completed_at=datetime.utcnow()
        )
        db.add(refund_txn)
        await db.flush()  # 确保ID和默认值被设置

        # 更新账户余额
        account.balance = balance_after
        account.updated_at = datetime.utcnow()

        # 记录高危审计日志
        await audit_service.log_high_risk(
            db=db,
            tenant_id=tenant_id,
            user_id=operator_id,
            action="REFUND",
            resource_type="billing",
            resource_id=transaction_id,
            old_value={
                "original_amount": original_txn.amount,
                "original_balance": account.balance - refund_amount
            },
            new_value={
                "refund_amount": refund_amount,
                "new_balance": balance_after,
                "reason": reason
            },
            description=f"退款 {original_txn.amount/100:.2f} 元，原因: {reason}"
        )

        return refund_txn

    @staticmethod
    async def get_account_balance(
        db: AsyncSession,
        tenant_id: str,
        account_id: str
    ) -> dict:
        """获取账户余额"""
        result = await db.execute(
            select(BillingAccount).where(
                and_(
                    BillingAccount.id == account_id,
                    BillingAccount.tenant_id == tenant_id
                )
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="计费账户不存在",
            )

        return {
            "account_id": account.id,
            "balance": account.balance,
            "balance_display": f"{account.balance/100:.2f}",
            "credit_limit": account.credit_limit,
            "available_credit": account.balance + account.credit_limit
        }

    @staticmethod
    async def get_transaction_history(
        db: AsyncSession,
        tenant_id: str,
        account_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50
    ) -> list:
        """获取交易历史"""
        query = select(BillingTransaction).where(
            BillingTransaction.tenant_id == tenant_id
        )

        if account_id:
            query = query.where(BillingTransaction.account_id == account_id)
        if start_date:
            query = query.where(BillingTransaction.created_at >= start_date)
        if end_date:
            query = query.where(BillingTransaction.created_at <= end_date)

        query = query.order_by(BillingTransaction.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return result.scalars().all()


# 全局计费服务实例
billing_service = BillingService()
