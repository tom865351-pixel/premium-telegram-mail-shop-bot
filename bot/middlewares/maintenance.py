from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import get_settings
from bot.services.settings import maintenance_enabled


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if not session or not await maintenance_enabled(session):
            return await handler(event, data)

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and user.id in get_settings().admin_ids:
            return await handler(event, data)

        text = "🛠 Maintenance Mode\n\nBot currently maintenance-e ache. Ektu pore abar try korun."
        if isinstance(event, CallbackQuery):
            await event.answer("Bot is under maintenance.", show_alert=True)
            if event.message:
                await event.message.answer(text)
            return None
        if isinstance(event, Message):
            await event.answer(text)
            return None

        return await handler(event, data)
