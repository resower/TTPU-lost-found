from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery

from . import queries
from .db import db
from .strings import t


class UserMiddleware(BaseMiddleware):
    """Before every handler: load (or create) the TelegramUser and stop blocked users."""

    async def __call__(self, handler, event, data):
        user = await db(queries.get_or_create_user, data["event_from_user"])
        if user.is_blocked:
            text = t(user.language, "blocked")
            if isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=True)
            else:
                await event.answer(text)
            return None
        data["user"] = user
        return await handler(event, data)
