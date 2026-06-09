from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Order, ReplacementRequest, ReplacementStatus, User


async def create_replacement_request(
    session: AsyncSession,
    user_id: int,
    order_id: int | None,
    quantity: int,
    message: str,
    proof_text: str | None = None,
    proof_file_id: str | None = None,
    proof_file_name: str | None = None,
) -> ReplacementRequest:
    request = ReplacementRequest(
        user_id=user_id,
        order_id=order_id,
        quantity=max(int(quantity), 1),
        message=message.strip(),
        proof_text=proof_text.strip() if proof_text else None,
        proof_file_id=proof_file_id,
        proof_file_name=proof_file_name,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def pending_replacements(session: AsyncSession, limit: int = 20) -> list[ReplacementRequest]:
    result = await session.execute(
        select(ReplacementRequest)
        .where(ReplacementRequest.status == ReplacementStatus.PENDING)
        .order_by(ReplacementRequest.id)
        .limit(limit)
    )
    return list(result.scalars().all())


async def recent_replacements(session: AsyncSession, user_id: int, limit: int = 10) -> list[ReplacementRequest]:
    result = await session.execute(
        select(ReplacementRequest)
        .where(ReplacementRequest.user_id == user_id)
        .order_by(ReplacementRequest.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def review_replacement(
    session: AsyncSession,
    request_id: int,
    approve: bool,
) -> tuple[bool, str, ReplacementRequest | None]:
    request = await session.get(ReplacementRequest, request_id)
    if not request or request.status != ReplacementStatus.PENDING:
        return False, "Replacement request not found or already reviewed.", request

    request.status = ReplacementStatus.APPROVED if approve else ReplacementStatus.REJECTED
    request.reviewed_at = datetime.utcnow()
    if approve:
        refund_amount = 0.0
        if request.order_id:
            order = await session.get(Order, request.order_id)
            if order:
                refund_amount = round(float(order.amount) * int(request.quantity), 2)
        request.refund_amount = refund_amount
        user = await session.get(User, request.user_id)
        if user and refund_amount > 0:
            user.balance = float(user.balance) + refund_amount
    await session.commit()
    await session.refresh(request)
    if approve:
        return True, "Replacement approved and balance refunded.", request
    return True, "Replacement request rejected.", request
