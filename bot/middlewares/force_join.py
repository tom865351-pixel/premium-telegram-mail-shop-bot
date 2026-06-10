from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot.config import get_settings

JOIN_CHECK_CALLBACK = "force_join_check"
ALLOWED_MEMBER_STATUSES = {"creator", "administrator", "member"}


def force_join_keyboard() -> InlineKeyboardMarkup:
    settings = get_settings()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel", url=settings.required_channel_link)],
            [InlineKeyboardButton(text="✅ I Joined", callback_data=JOIN_CHECK_CALLBACK)],
        ]
    )


def force_join_text() -> str:
    return (
        "📢 Channel Join Required\n\n"
        "Bot use korte hole age amader channel join korte hobe.\n\n"
        f"Channel: {get_settings().required_channel_link}\n\n"
        "Join korar por ✅ I Joined button press korun."
    )


async def is_channel_member(bot: Any, user_id: int) -> bool:
    settings = get_settings()
    channel = settings.required_channel_username.strip() or settings.required_channel_link.strip()
    if not settings.force_join_enabled or not channel:
        return True
    if user_id in settings.admin_ids:
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return False
    status = getattr(member.status, "value", member.status)
    return status in ALLOWED_MEMBER_STATUSES


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        if not settings.force_join_enabled:
            return await handler(event, data)

        user = None
        bot = data.get("bot")
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            if event.data == JOIN_CHECK_CALLBACK:
                return await handler(event, data)

        if not user or not bot or user.id in settings.admin_ids:
            return await handler(event, data)

        if await is_channel_member(bot, user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer("Please join the channel first.", show_alert=True)
            if event.message:
                await event.message.answer(force_join_text(), reply_markup=force_join_keyboard())
            return None

        await event.answer(force_join_text(), reply_markup=force_join_keyboard())
        return None
