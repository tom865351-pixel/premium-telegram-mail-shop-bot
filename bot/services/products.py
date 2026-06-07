from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Product, StockItem


async def list_active_products(session: AsyncSession) -> list[tuple[Product, int]]:
    result = await session.execute(
        select(Product, func.count(StockItem.id))
        .outerjoin(StockItem, (StockItem.product_id == Product.id) & (StockItem.is_sold.is_(False)))
        .where(Product.is_active.is_(True))
        .group_by(Product.id)
        .order_by(Product.name)
    )
    return [(product, int(stock_count)) for product, stock_count in result.all()]


async def list_all_products(session: AsyncSession) -> list[tuple[Product, int]]:
    result = await session.execute(
        select(Product, func.count(StockItem.id))
        .outerjoin(StockItem, (StockItem.product_id == Product.id) & (StockItem.is_sold.is_(False)))
        .group_by(Product.id)
        .order_by(Product.id.desc())
    )
    return [(product, int(stock_count)) for product, stock_count in result.all()]


async def create_product(session: AsyncSession, name: str, price: float, description: str) -> Product:
    product = Product(name=name.strip(), price=price, description=description.strip())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def add_stock(session: AsyncSession, product_id: int, lines: list[str]) -> int:
    clean_lines = [line.strip() for line in lines if line.strip()]
    session.add_all([StockItem(product_id=product_id, payload=line) for line in clean_lines])
    await session.commit()
    return len(clean_lines)


async def toggle_product(session: AsyncSession, product_id: int) -> Product | None:
    product = await session.get(Product, product_id)
    if not product:
        return None
    product.is_active = not product.is_active
    await session.commit()
    await session.refresh(product)
    return product


async def reserve_stock_item(session: AsyncSession, product_id: int) -> StockItem | None:
    stock_item = await session.scalar(
        select(StockItem)
        .where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
        .order_by(StockItem.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if stock_item:
        stock_item.is_sold = True
        stock_item.sold_at = datetime.utcnow()
    return stock_item
