from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.models import Order, Product, ReferralReward, StockItem, User
from bot.services.products import reserve_stock_item


async def purchase_product(session: AsyncSession, user: User, product_id: int) -> tuple[bool, str, StockItem | None]:
    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        return False, "Product is unavailable.", None

    price = float(product.price)
    if float(user.balance) < price:
        return False, "Insufficient balance. Please deposit first.", None

    stock_item = await reserve_stock_item(session, product_id)
    if not stock_item:
        return False, "This product is out of stock.", None

    user.balance = float(user.balance) - price
    order = Order(user_id=user.id, product_id=product.id, stock_item_id=stock_item.id, amount=price)
    session.add(order)
    await session.flush()
    stock_item.sold_order_id = order.id

    if user.referred_by_id:
        settings = get_settings()
        reward_amount = round(price * settings.referral_commission_percent / 100, 2)
        if reward_amount > 0:
            referrer = await session.get(User, user.referred_by_id)
            if referrer:
                referrer.balance = float(referrer.balance) + reward_amount
                session.add(
                    ReferralReward(
                        referrer_id=referrer.id,
                        referred_user_id=user.id,
                        order_id=order.id,
                        amount=reward_amount,
                    )
                )

    await session.commit()
    return True, "Purchase completed.", stock_item


async def recent_orders(session: AsyncSession, user_id: int, limit: int = 10) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def order_count(session: AsyncSession, user_id: int) -> int:
    return int(await session.scalar(select(func.count(Order.id)).where(Order.user_id == user_id)) or 0)
