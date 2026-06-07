from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Deposit, DepositStatus, Order, Product, StockItem, User


async def admin_stats(session: AsyncSession) -> dict[str, float | int]:
    users = int(await session.scalar(select(func.count(User.id))) or 0)
    products = int(await session.scalar(select(func.count(Product.id))) or 0)
    stock = int(await session.scalar(select(func.count(StockItem.id)).where(StockItem.is_sold.is_(False))) or 0)
    orders = int(await session.scalar(select(func.count(Order.id))) or 0)
    revenue = float(await session.scalar(select(func.coalesce(func.sum(Order.amount), 0))) or 0)
    pending_deposits = int(
        await session.scalar(select(func.count(Deposit.id)).where(Deposit.status == DepositStatus.PENDING)) or 0
    )
    return {
        "users": users,
        "products": products,
        "stock": stock,
        "orders": orders,
        "revenue": revenue,
        "pending_deposits": pending_deposits,
    }
