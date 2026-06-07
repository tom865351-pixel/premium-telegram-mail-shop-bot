from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.models import Order, Product, ReferralReward, StockItem, User
from bot.services.products import reserve_stock_item, reserve_stock_items


async def purchase_product(session: AsyncSession, user: User, product_id: int) -> tuple[bool, str, StockItem | None]:
    if getattr(user, "is_banned", False):
        return False, "Your account is banned. Please contact support.", None
    if getattr(user, "is_restricted", False):
        return False, "Your account is restricted. Please contact support.", None

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


async def purchase_product_bulk(
    session: AsyncSession,
    user: User,
    product_id: int,
    quantity: int,
) -> tuple[bool, str, list[StockItem]]:
    if getattr(user, "is_banned", False):
        return False, "Your account is banned. Please contact support.", []
    if getattr(user, "is_restricted", False):
        return False, "Your account is restricted. Please contact support.", []

    if quantity < 2:
        return False, "Bulk buy quantity must be at least 2.", []

    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        return False, "Product is unavailable.", []

    unit_price = float(product.price)
    total_price = round(unit_price * quantity, 2)
    if float(user.balance) < total_price:
        return False, f"Insufficient balance. Need {total_price:.2f}.", []

    stock_items = await reserve_stock_items(session, product_id, quantity)
    if len(stock_items) < quantity:
        await session.rollback()
        return False, f"Only {len(stock_items)} item(s) available in stock.", []

    user.balance = float(user.balance) - total_price
    orders = []
    for stock_item in stock_items:
        order = Order(user_id=user.id, product_id=product.id, stock_item_id=stock_item.id, amount=unit_price)
        session.add(order)
        orders.append((order, stock_item))

    await session.flush()
    for order, stock_item in orders:
        stock_item.sold_order_id = order.id

    if user.referred_by_id:
        settings = get_settings()
        reward_amount = round(total_price * settings.referral_commission_percent / 100, 2)
        if reward_amount > 0:
            referrer = await session.get(User, user.referred_by_id)
            if referrer:
                referrer.balance = float(referrer.balance) + reward_amount
                for order, _ in orders:
                    session.add(
                        ReferralReward(
                            referrer_id=referrer.id,
                            referred_user_id=user.id,
                            order_id=order.id,
                            amount=round(float(order.amount) * settings.referral_commission_percent / 100, 2),
                        )
                    )

    await session.commit()
    return True, "Bulk purchase completed.", stock_items


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


async def spent_today(session: AsyncSession, user_id: int) -> float:
    today_start = datetime.combine(datetime.utcnow().date(), time.min)
    total = await session.scalar(
        select(func.coalesce(func.sum(Order.amount), 0)).where(
            Order.user_id == user_id,
            Order.created_at >= today_start,
        )
    )
    return float(total or 0)


async def total_spent(session: AsyncSession, user_id: int) -> float:
    total = await session.scalar(
        select(func.coalesce(func.sum(Order.amount), 0)).where(Order.user_id == user_id)
    )
    return float(total or 0)
