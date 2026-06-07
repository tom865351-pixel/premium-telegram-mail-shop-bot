from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Deposit, DepositStatus, User


async def create_deposit(
    session: AsyncSession,
    user_id: int,
    amount: float,
    method: str,
    transaction_id: str,
) -> Deposit:
    deposit = Deposit(user_id=user_id, amount=amount, method=method, transaction_id=transaction_id)
    session.add(deposit)
    await session.commit()
    await session.refresh(deposit)
    return deposit


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
