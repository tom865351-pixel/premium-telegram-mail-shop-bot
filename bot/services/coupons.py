from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Coupon, CouponRedemption, User
from bot.services.settings import coupons_enabled


async def create_coupon(session: AsyncSession, code: str, amount: float, max_uses: int) -> Coupon:
    coupon = Coupon(code=code.upper().strip(), amount=amount, max_uses=max_uses)
    session.add(coupon)
    await session.commit()
    await session.refresh(coupon)
    return coupon


async def redeem_coupon(session: AsyncSession, user: User, code: str) -> tuple[bool, str]:
    if not await coupons_enabled(session):
        return False, "Coupon system is currently turned off."
    coupon = await session.scalar(select(Coupon).where(Coupon.code == code.upper().strip()))
    if not coupon or not coupon.is_active:
        return False, "Coupon not found or inactive."
    if coupon.used_count >= coupon.max_uses:
        return False, "Coupon usage limit reached."

    coupon.used_count += 1
    user.balance = float(user.balance) + float(coupon.amount)
    session.add(CouponRedemption(coupon_id=coupon.id, user_id=user.id))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return False, "You already used this coupon."
    return True, f"Coupon redeemed. Added {float(coupon.amount):.2f} to your balance."
