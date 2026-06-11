import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import get_settings


class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._last_seen: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        if settings.anti_spam_seconds <= 0:
            return await handler(event, data)

        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user or user.id in settings.admin_ids:
            return await handler(event, data)

        now = time.monotonic()
        previous = self._last_seen.get(user.id, 0)
        if now - previous < settings.anti_spam_seconds:
            if isinstance(event, CallbackQuery):
                await event.answer("Slow down a little.", show_alert=False)
            return None
        self._last_seen[user.id] = now
        return await handler(event, data)
