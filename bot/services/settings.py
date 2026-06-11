from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BotSetting

COUPON_ENABLED_KEY = "coupon_enabled"
MAINTENANCE_ENABLED_KEY = "maintenance_enabled"
STORE_NOTICE_KEY = "store_notice"
SELL_ENABLED_KEY = "sell_enabled"


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


async def maintenance_enabled(session: AsyncSession) -> bool:
    return (await get_setting(session, MAINTENANCE_ENABLED_KEY, "off")).lower() == "on"


async def set_maintenance_enabled(session: AsyncSession, enabled: bool) -> None:
    await set_setting(session, MAINTENANCE_ENABLED_KEY, "on" if enabled else "off")


async def get_store_notice(session: AsyncSession) -> str:
    return await get_setting(session, STORE_NOTICE_KEY, "")


async def set_store_notice(session: AsyncSession, notice: str) -> None:
    await set_setting(session, STORE_NOTICE_KEY, notice.strip())


async def sell_enabled(session: AsyncSession) -> bool:
    return (await get_setting(session, SELL_ENABLED_KEY, "on")).lower() == "on"


async def set_sell_enabled(session: AsyncSession, enabled: bool) -> None:
    await set_setting(session, SELL_ENABLED_KEY, "on" if enabled else "off")
