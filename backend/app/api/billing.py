"""
计费管理API
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import (
    get_current_active_user,
    TenantIsolation,
    PermissionChecker
)
from app.models.user import User
from app.models.billing import BillingAccount, BillingTransaction
from app.services.billing_service import billing_service

router = APIRouter()


class AccountCreateRequest(BaseModel):
    user_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    account_type: str = "individual"
    credit_limit: int = 0


class AccountResponse(BaseModel):
    id: str
    user_id: Optional[str]
    vehicle_id: Optional[str]
    account_type: str
    balance: int
    balance_display: str
    credit_limit: int
    status: str
    created_at: datetime


class PaymentRequest(BaseModel):
    account_id: str
    amount: int
    payment_method: str
    description: Optional[str] = None


class RefundRequest(BaseModel):
    transaction_id: str
    reason: str


class TransactionResponse(BaseModel):
    id: str
    account_id: str
    vehicle_log_id: Optional[str]
    transaction_type: str
    amount: int
    amount_display: str
    balance_after: int
    balance_after_display: str
    description: Optional[str]
    payment_method: Optional[str]
    status: str
    created_at: datetime


class BalanceResponse(BaseModel):
    account_id: str
    balance: int
    balance_display: str
    credit_limit: int
    available_credit: int


@router.post("/accounts", response_model=AccountResponse)
async def create_account(
    request: Request,
    account_data: AccountCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:write"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """创建计费账户"""
    account = await billing_service.create_account(
        db=db,
        tenant_id=tenant_id,
        user_id=account_data.user_id,
        vehicle_id=account_data.vehicle_id,
        account_type=account_data.account_type,
        credit_limit=account_data.credit_limit
    )

    return AccountResponse(
        id=account.id,
        user_id=account.user_id,
        vehicle_id=account.vehicle_id,
        account_type=account.account_type,
        balance=account.balance,
        balance_display=f"{account.balance/100:.2f}",
        credit_limit=account.credit_limit,
        status=account.status,
        created_at=account.created_at
    )


@router.get("/accounts", response_model=List[AccountResponse])
async def get_accounts(
    user_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取计费账户列表"""
    query = select(BillingAccount).where(BillingAccount.tenant_id == tenant_id)

    if user_id:
        query = query.where(BillingAccount.user_id == user_id)
    if vehicle_id:
        query = query.where(BillingAccount.vehicle_id == vehicle_id)

    result = await db.execute(query)
    accounts = result.scalars().all()

    return [
        AccountResponse(
            id=account.id,
            user_id=account.user_id,
            vehicle_id=account.vehicle_id,
            account_type=account.account_type,
            balance=account.balance,
            balance_display=f"{account.balance/100:.2f}",
            credit_limit=account.credit_limit,
            status=account.status,
            created_at=account.created_at
        )
        for account in accounts
    ]


@router.post("/payment", response_model=TransactionResponse)
async def process_payment(
    request: Request,
    payment_data: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:payment"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """处理支付（充值）"""
    transaction = await billing_service.process_payment(
        db=db,
        tenant_id=tenant_id,
        account_id=payment_data.account_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        operator_id=current_user.id,
        description=payment_data.description
    )

    return TransactionResponse(
        id=transaction.id,
        account_id=transaction.account_id,
        vehicle_log_id=transaction.vehicle_log_id,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        amount_display=f"{transaction.amount/100:.2f}",
        balance_after=transaction.balance_after,
        balance_after_display=f"{transaction.balance_after/100:.2f}",
        description=transaction.description,
        payment_method=transaction.payment_method,
        status=transaction.status,
        created_at=transaction.created_at
    )


@router.post("/refund", response_model=TransactionResponse)
async def process_refund(
    request: Request,
    refund_data: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:refund"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """处理退款（高危操作）"""
    transaction = await billing_service.process_refund(
        db=db,
        tenant_id=tenant_id,
        transaction_id=refund_data.transaction_id,
        operator_id=current_user.id,
        reason=refund_data.reason
    )

    return TransactionResponse(
        id=transaction.id,
        account_id=transaction.account_id,
        vehicle_log_id=transaction.vehicle_log_id,
        transaction_type=transaction.transaction_type,
        amount=transaction.amount,
        amount_display=f"{transaction.amount/100:.2f}",
        balance_after=transaction.balance_after,
        balance_after_display=f"{transaction.balance_after/100:.2f}",
        description=transaction.description,
        payment_method=transaction.payment_method,
        status=transaction.status,
        created_at=transaction.created_at
    )


@router.get("/accounts/{account_id}/balance", response_model=BalanceResponse)
async def get_account_balance(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取账户余额"""
    balance_data = await billing_service.get_account_balance(db, tenant_id, account_id)
    return BalanceResponse(**balance_data)


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    account_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(PermissionChecker(["billing:read"])),
    tenant_id: str = Depends(TenantIsolation())
):
    """获取交易记录"""
    transactions = await billing_service.get_transaction_history(
        db=db,
        tenant_id=tenant_id,
        account_id=account_id,
        vehicle_id=vehicle_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    return [
        TransactionResponse(
            id=txn.id,
            account_id=txn.account_id,
            vehicle_log_id=txn.vehicle_log_id,
            transaction_type=txn.transaction_type,
            amount=txn.amount,
            amount_display=f"{txn.amount/100:.2f}",
            balance_after=txn.balance_after,
            balance_after_display=f"{txn.balance_after/100:.2f}",
            description=txn.description,
            payment_method=txn.payment_method,
            status=txn.status,
            created_at=txn.created_at
        )
        for txn in transactions
    ]
