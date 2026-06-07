from secrets import token_hex

from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User


async def get_or_create_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
    referral_code: str | None = None,
) -> User:
    existing = await session.scalar(select(User).where(User.telegram_id == telegram_user.id))
    if existing:
        existing.username = telegram_user.username
        existing.first_name = telegram_user.first_name
        await session.commit()
        return existing

    referred_by_id = None
    if referral_code:
        referrer = await session.scalar(select(User).where(User.referral_code == referral_code))
        if referrer and referrer.telegram_id != telegram_user.id:
            referred_by_id = referrer.id

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        referral_code=token_hex(4),
        referred_by_id=referred_by_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def list_recent_users(session: AsyncSession, limit: int = 20) -> list[User]:
    result = await session.execute(select(User).order_by(User.id.desc()).limit(limit))
    return list(result.scalars().all())


async def list_all_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.id))
    return list(result.scalars().all())


async def find_user(session: AsyncSession, query: str) -> User | None:
    clean = query.strip()
    if clean.startswith("@"):
        clean = clean[1:]
    if clean.isdigit():
        return await get_user_by_telegram_id(session, int(clean))
    return await session.scalar(select(User).where(User.username.ilike(clean)))


async def adjust_user_balance(session: AsyncSession, user_id: int, amount: float) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.balance = round(float(user.balance) + amount, 2)
    if float(user.balance) < 0:
        user.balance = 0
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_note(session: AsyncSession, user_id: int, note: str) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.admin_note = note.strip() or None
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_banned(session: AsyncSession, user_id: int, banned: bool) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.is_banned = banned
    await session.commit()
    await session.refresh(user)
    return user


async def set_user_restricted(session: AsyncSession, user_id: int, restricted: bool) -> User | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    user.is_restricted = restricted
    await session.commit()
    await session.refresh(user)
    return user
