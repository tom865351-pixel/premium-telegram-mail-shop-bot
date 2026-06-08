from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Order, Product, StockItem


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
        .where(Product.name.not_like("[deleted #%"))
        .group_by(Product.id)
        .order_by(Product.id.desc())
    )
    return [(product, int(stock_count)) for product, stock_count in result.all()]


async def search_products(session: AsyncSession, query: str, limit: int = 10) -> list[tuple[Product, int]]:
    clean = query.strip()
    statement = (
        select(Product, func.count(StockItem.id))
        .outerjoin(StockItem, (StockItem.product_id == Product.id) & (StockItem.is_sold.is_(False)))
        .where(Product.name.not_like("[deleted #%"))
        .group_by(Product.id)
        .order_by(Product.id.desc())
        .limit(limit)
    )
    if clean.isdigit():
        statement = statement.where(Product.id == int(clean))
    else:
        statement = statement.where(Product.name.ilike(f"%{clean}%"))
    result = await session.execute(statement)
    return [(product, int(stock_count)) for product, stock_count in result.all()]


async def unsold_stock_items(session: AsyncSession, product_id: int) -> list[StockItem]:
    result = await session.execute(
        select(StockItem)
        .where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
        .order_by(StockItem.id)
    )
    return list(result.scalars().all())


async def create_product(session: AsyncSession, name: str, price: float, description: str) -> Product:
    product = Product(name=name.strip(), price=price, description=description.strip())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(
    session: AsyncSession,
    product_id: int,
    name: str,
    price: float,
    description: str,
) -> Product | None:
    product = await session.get(Product, product_id)
    if not product:
        return None
    product.name = name.strip()
    product.price = price
    product.description = description.strip()
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("A product with this name already exists.") from exc
    await session.refresh(product)
    return product


async def add_stock(session: AsyncSession, product_id: int, lines: list[str]) -> int:
    clean_lines = [line.strip() for line in lines if line.strip()]
    session.add_all([StockItem(product_id=product_id, payload=line) for line in clean_lines])
    await session.commit()
    return len(clean_lines)


async def unsold_stock_count(session: AsyncSession, product_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count(StockItem.id)).where(
                StockItem.product_id == product_id,
                StockItem.is_sold.is_(False),
            )
        )
        or 0
    )


async def toggle_product(session: AsyncSession, product_id: int) -> Product | None:
    product = await session.get(Product, product_id)
    if not product:
        return None
    product.is_active = not product.is_active
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product_id: int) -> tuple[bool, str]:
    product = await session.get(Product, product_id)
    if not product:
        return False, "Product not found."

    order_count = int(await session.scalar(select(func.count(Order.id)).where(Order.product_id == product_id)) or 0)
    if order_count:
        archived_name = f"[deleted #{product.id}] {product.name}"
        product.name = archived_name[:255]
        product.is_active = False
        await session.execute(
            delete(StockItem).where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
        )
        await session.commit()
        return True, "Product archived and removed from the product list. Old order history was kept safe."

    await session.execute(delete(StockItem).where(StockItem.product_id == product_id))
    await session.delete(product)
    await session.commit()
    return True, "Product deleted."


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


async def reserve_stock_items(session: AsyncSession, product_id: int, quantity: int) -> list[StockItem]:
    result = await session.execute(
        select(StockItem)
        .where(StockItem.product_id == product_id, StockItem.is_sold.is_(False))
        .order_by(StockItem.id)
        .with_for_update(skip_locked=True)
        .limit(quantity)
    )
    stock_items = list(result.scalars().all())
    for stock_item in stock_items:
        stock_item.is_sold = True
        stock_item.sold_at = datetime.utcnow()
    return stock_items
