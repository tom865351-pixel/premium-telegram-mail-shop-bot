from datetime import datetime, time
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.models import Order, OrderStatus, Product, ReferralReward, StockItem, User
from bot.services.products import reserve_stock_item, reserve_stock_items


async def vip_discount_percent(session: AsyncSession, user_id: int) -> float:
    settings = get_settings()
    spent = float(
        await session.scalar(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.user_id == user_id,
                Order.status == OrderStatus.COMPLETED,
            )
        )
        or 0
    )
    if spent >= settings.vip_gold_spend:
        return float(settings.vip_gold_discount_percent)
    if spent >= settings.vip_silver_spend:
        return float(settings.vip_silver_discount_percent)
    return 0.0


async def vip_price(session: AsyncSession, user_id: int, price: float) -> float:
    discount = await vip_discount_percent(session, user_id)
    if discount <= 0:
        return round(float(price), 2)
    return round(float(price) * (100 - discount) / 100, 2)


async def purchase_product(session: AsyncSession, user: User, product_id: int) -> tuple[bool, str, StockItem | None]:
    if getattr(user, "is_banned", False):
        return False, "Your account is banned. Please contact support.", None
    if getattr(user, "is_restricted", False):
        return False, "Your account is restricted. Please contact support.", None

    product = await session.get(Product, product_id)
    if not product or not product.is_active:
        return False, "Product is unavailable.", None

    price = await vip_price(session, user.id, float(product.price))
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
    await session.refresh(order)
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

    unit_price = await vip_price(session, user.id, float(product.price))
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


async def refund_order(session: AsyncSession, order_id: int) -> tuple[bool, str, Order | None]:
    order = await session.get(Order, order_id)
    if not order:
        return False, "Order not found.", None
    if order.status == OrderStatus.REFUNDED:
        return False, "Order already refunded.", order
    user = await session.get(User, order.user_id)
    if not user:
        return False, "Order user not found.", order
    order.status = OrderStatus.REFUNDED
    user.balance = float(user.balance) + float(order.amount)
    await session.commit()
    await session.refresh(order)
    return True, "Order refunded and balance returned.", order


async def sales_report(session: AsyncSession, days: int = 1) -> dict[str, float | int]:
    start = datetime.utcnow() - timedelta(days=days)
    orders_total = int(await session.scalar(select(func.count(Order.id)).where(Order.created_at >= start)) or 0)
    revenue = float(
        await session.scalar(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.created_at >= start,
                Order.status == OrderStatus.COMPLETED,
            )
        )
        or 0
    )
    refunded = float(
        await session.scalar(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.created_at >= start,
                Order.status == OrderStatus.REFUNDED,
            )
        )
        or 0
    )
    return {"days": days, "orders": orders_total, "revenue": revenue, "refunded": refunded}


async def recent_orders(session: AsyncSession, user_id: int, limit: int = 10) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def recent_order_groups(session: AsyncSession, user_id: int, limit: int = 15) -> list[dict[str, object]]:
    result = await session.execute(
        select(Order, Product.name, StockItem.payload)
        .join(Product, Product.id == Order.product_id)
        .join(StockItem, StockItem.id == Order.stock_item_id)
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .limit(2000)
    )
    groups: dict[tuple[int, float, str, str], dict[str, object]] = {}
    ordered_keys: list[tuple[int, float, str, str]] = []
    for order, product_name, payload in result.all():
        minute_key = order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else ""
        key = (order.product_id, float(order.amount), order.status.value, minute_key)
        if key not in groups:
            groups[key] = {
                "product_name": product_name,
                "quantity": 0,
                "unit_price": float(order.amount),
                "total": 0.0,
                "status": order.status.value,
                "created_at": order.created_at,
                "items": [],
            }
            ordered_keys.append(key)
        groups[key]["quantity"] = int(groups[key]["quantity"]) + 1
        groups[key]["total"] = float(groups[key]["total"]) + float(order.amount)
        groups[key]["items"].append(payload)
    return [groups[key] for key in ordered_keys[:limit]]


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    return await session.get(Order, order_id)


async def all_orders(session: AsyncSession, limit: int = 500) -> list[Order]:
    result = await session.execute(select(Order).order_by(Order.id.desc()).limit(limit))
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
