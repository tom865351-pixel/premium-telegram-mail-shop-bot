from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Deposit, DepositStatus, User


async def create_deposit(
    session: AsyncSession,
    user_id: int,
    amount: float,
    method: str,
    transaction_id: str,
    proof_file_id: str | None = None,
    ocr_status: str | None = None,
    ocr_details: str | None = None,
    status: DepositStatus = DepositStatus.PENDING,
) -> Deposit:
    deposit = Deposit(
        user_id=user_id,
        amount=amount,
        method=method,
        transaction_id=transaction_id.strip(),
        proof_file_id=proof_file_id,
        ocr_status=ocr_status,
        ocr_details=ocr_details,
        status=status,
    )
    if status == DepositStatus.APPROVED:
        deposit.reviewed_at = datetime.utcnow()
        user = await session.get(User, user_id)
        if user:
            user.balance = float(user.balance) + float(amount)
    session.add(deposit)
    await session.commit()
    await session.refresh(deposit)
    return deposit


async def txid_exists(session: AsyncSession, transaction_id: str) -> bool:
    normalized = transaction_id.strip().lower()
    if not normalized:
        return False
    existing = await session.scalar(
        select(Deposit.id).where(func.lower(Deposit.transaction_id) == normalized).limit(1)
    )
    return existing is not None


async def approved_deposit_count(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.count(Deposit.id)).where(
            Deposit.user_id == user_id,
            Deposit.status == DepositStatus.APPROVED,
        )
    )
    return int(total or 0)


async def pending_deposits(session: AsyncSession, limit: int = 20) -> list[Deposit]:
    result = await session.execute(
        select(Deposit)
        .where(Deposit.status == DepositStatus.PENDING)
        .order_by(Deposit.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def review_deposit(session: AsyncSession, deposit_id: int, approve: bool) -> Deposit | None:
    deposit = await session.get(Deposit, deposit_id)
    if not deposit or deposit.status != DepositStatus.PENDING:
        return None

    deposit.status = DepositStatus.APPROVED if approve else DepositStatus.REJECTED
    deposit.reviewed_at = datetime.utcnow()
    if approve:
        user = await session.get(User, deposit.user_id)
        if user:
            user.balance = float(user.balance) + float(deposit.amount)
    await session.commit()
    await session.refresh(deposit)
    return deposit


async def deposited_today(session: AsyncSession, user_id: int) -> float:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    total = await session.scalar(
        select(func.coalesce(func.sum(Deposit.amount), 0)).where(
            Deposit.user_id == user_id,
            Deposit.status == DepositStatus.APPROVED,
            Deposit.reviewed_at >= today_start,
        )
    )
    return float(total or 0)
