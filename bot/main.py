import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_settings
from bot.database import models  # noqa: F401
from bot.database.session import init_db
from bot.handlers import setup_routers
from bot.middlewares.database import DatabaseMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    await init_db()
    logging.info("PostgreSQL connection ready and tables initialized")

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()
    dispatcher.update.middleware(DatabaseMiddleware())
    dispatcher.include_router(setup_routers())

    logging.info("Telegram Mail Shop Bot started")
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
