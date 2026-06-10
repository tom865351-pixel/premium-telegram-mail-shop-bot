from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BotSetting

COUPON_ENABLED_KEY = "coupon_enabled"


async def get_setting(session: AsyncSession, key: str, default: str = "") -> str:
    setting = await session.get(BotSetting, key)
    return setting.value if setting else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    setting = await session.get(BotSetting, key)
    if setting:
        setting.value = value
    else:
        session.add(BotSetting(key=key, value=value))
    await session.commit()


async def coupons_enabled(session: AsyncSession) -> bool:
    return (await get_setting(session, COUPON_ENABLED_KEY, "on")).lower() == "on"


async def set_coupons_enabled(session: AsyncSession, enabled: bool) -> None:
    await set_setting(session, COUPON_ENABLED_KEY, "on" if enabled else "off")
