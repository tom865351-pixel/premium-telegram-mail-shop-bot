import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.database import models  # noqa: F401
from bot.database.session import init_db
from bot.handlers import setup_routers
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.anti_spam import AntiSpamMiddleware
from bot.middlewares.force_join import ForceJoinMiddleware
from bot.middlewares.maintenance import MaintenanceMiddleware
from bot.services.auto_stock import auto_stock_worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    await init_db()
    logging.info("PostgreSQL connection ready and tables initialized")

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.update.middleware(DatabaseMiddleware())
    dispatcher.message.middleware(MaintenanceMiddleware())
    dispatcher.callback_query.middleware(MaintenanceMiddleware())
    dispatcher.message.middleware(AntiSpamMiddleware())
    dispatcher.callback_query.middleware(AntiSpamMiddleware())
    dispatcher.message.middleware(ForceJoinMiddleware())
    dispatcher.callback_query.middleware(ForceJoinMiddleware())
    dispatcher.include_router(setup_routers())

    logging.info("Telegram Mail Shop Bot started")
    async def notify_admin(admin_id: int, text: str) -> None:
        with suppress(Exception):
            await bot.send_message(admin_id, text)

    auto_stock_task = None
    if settings.admin_ids:
        auto_stock_task = asyncio.create_task(auto_stock_worker(settings.admin_ids, notify_admin))
        logging.info("Auto stock refill worker started")

    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        if auto_stock_task:
            auto_stock_task.cancel()
            with suppress(asyncio.CancelledError):
                await auto_stock_task
